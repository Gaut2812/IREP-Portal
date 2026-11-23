"""Screen 48 · Audit and consent. Spec: docs/screens/48-audit-and-consent.md

- IREP staff: read-only audit trail (+ CSV), consent overview, data-request queue.
- College admin (Screen 02 side, link L27): raise and follow export/deletion requests.
- Parent (own child) / student (self): record consent.

The audit log has no write or delete endpoint here, ever (CERT-In: keep 180 days).
"""
import csv
import datetime
import io
import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, is_super_admin, normalize_role, require_role
from core.tenant import get_child_for_parent, get_student_for_user
from models.schema import (AuditLog, CodingSubmission, ConsentRecord, DataRequest, ParentStudent,
                           SessionAttendance, Student, TestAttempt, User, Certificate)
from services import consent as consent_svc
from services.audit import record_audit
from services.support_access import colleges_with_session, require_session
from services.notifications import notify_user
from services.outbox import emit, handler as outbox_handler
from services.storage import get_storage

router = APIRouter(tags=["Screen 48 · Audit and consent"])
STAFF = require_role(["irep_admin"])
COLLEGE = require_role(["college_admin"])
REQUEST_DAYS = 30            # DPDP handling target (to confirm with legal; docs/screens/48)
MAX_PAGE = 200


# ---------------------------------------------------------------------------
# Audit trail (staff, read-only)
# ---------------------------------------------------------------------------

def _audit_query(college_id, actor, action, entity_id, date_from, date_to):
    q = select(AuditLog)
    if college_id:
        q = q.where(AuditLog.college_id == college_id)
    if actor:
        q = q.where(AuditLog.actor_user_id == actor)
    if action:
        q = q.where(AuditLog.action.like(action.rstrip("*") + "%"))
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if date_from:
        q = q.where(AuditLog.created_at >= datetime.datetime.combine(date_from, datetime.time.min))
    if date_to:
        q = q.where(AuditLog.created_at < datetime.datetime.combine(date_to + datetime.timedelta(days=1), datetime.time.min))
    return q


def _audit_row(a: AuditLog, names: dict) -> dict:
    return {"id": a.id, "at": a.created_at.isoformat(), "college_id": a.college_id, "actor_user_id": a.actor_user_id,
            "actor_name": names.get(a.actor_user_id), "actor_role": a.actor_role, "action": a.action,
            "entity_type": a.entity_type, "entity_id": a.entity_id, "detail": a.detail, "ip_address": a.ip_address}


def _support_access(db: Session, user: TokenPayload, college_id: Optional[str], what: str) -> None:
    """Staff looking at one college's records is itself audited (§5.4 'support access, logged')."""
    if college_id:
        record_audit(db, user, "support.access", "college", college_id, {"view": what}, college_id=college_id)


@router.get("/admin/audit")
def audit_trail(
    college_id: Optional[str] = None, actor: Optional[str] = None, action: Optional[str] = None,
    entity_id: Optional[str] = None, date_from: Optional[datetime.date] = None, date_to: Optional[datetime.date] = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=MAX_PAGE),
    current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db),
):
    q = _audit_query(college_id, actor, action, entity_id, date_from, date_to)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(q.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                      .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_({r.actor_user_id for r in rows if r.actor_user_id} or {"_"}))).all())
    # student and parent names only for colleges with an open support session (ids stay)
    open_for = colleges_with_session(db, current_user, {r.college_id for r in rows})
    for r in rows:
        if r.actor_role in ("student", "parent") and r.college_id not in open_for:
            names.pop(r.actor_user_id, None)
    _support_access(db, current_user, college_id, "audit_trail")
    db.commit()
    return {"total": total, "page": page, "page_size": page_size, "items": [_audit_row(r, names) for r in rows]}


@router.get("/admin/audit/export.csv")
def audit_export(
    college_id: Optional[str] = None, actor: Optional[str] = None, action: Optional[str] = None,
    entity_id: Optional[str] = None, date_from: Optional[datetime.date] = None, date_to: Optional[datetime.date] = None,
    current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db),
):
    q = _audit_query(college_id, actor, action, entity_id, date_from, date_to).order_by(AuditLog.created_at.desc()).limit(50_000)
    rows = db.execute(q).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["at", "college_id", "actor_user_id", "actor_role", "action", "entity_type", "entity_id", "detail", "ip_address"])
    for a in rows:
        w.writerow([a.created_at.isoformat(), a.college_id, a.actor_user_id or "", a.actor_role or "", a.action,
                    a.entity_type or "", a.entity_id or "", json.dumps(a.detail, ensure_ascii=False) if a.detail else "", a.ip_address or ""])
    record_audit(db, current_user, "audit.exported", "audit_log", None,
                 {"rows": len(rows), "filters": {"college_id": college_id, "actor": actor, "action": action, "entity_id": entity_id,
                                                  "date_from": str(date_from or ""), "date_to": str(date_to or "")}},
                 college_id=college_id or current_user.college_id)
    db.commit()
    return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="irep-audit.csv"'})


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------

class ConsentIn(BaseModel):
    purpose: str
    status: str = Field(pattern="^(granted|withdrawn)$")
    student_id: Optional[str] = None          # parents name the child; students record for themselves


def _subject_for(current_user: TokenPayload, db: Session, student_id: Optional[str]) -> Student:
    role = normalize_role(current_user.role)
    if role == "parent":
        return get_child_for_parent(current_user, db, student_id)          # not linked -> 404
    if role == "student":
        me = get_student_for_user(current_user, db)
        if student_id and student_id != me.id:
            raise HTTPException(status_code=404, detail="Student not found")
        return me
    raise HTTPException(status_code=403, detail="Only a parent or the student can record consent")


PARENTAL = {"code": "parental_consent_required",
            "message": "A parent must agree to this first, because the student is under 18. A request has been sent to the parent.",
            "message_ta": "மாணவர் 18 வயதுக்குக் குறைவானவர் என்பதால் முதலில் பெற்றோர் ஒப்புதல் தேவை. பெற்றோருக்குக் கோரிக்கை அனுப்பப்பட்டுள்ளது."}
REAUTH = {"code": "reauth_required",
          "message": "To give consent, sign in again with the code sent to your mobile number (it confirms it is you).",
          "message_ta": "ஒப்புதல் தர, உங்கள் கைபேசி எண்ணுக்கு வரும் குறியீட்டுடன் மீண்டும் உள்நுழையுங்கள் (அது நீங்கள்தான் என்பதை உறுதி செய்யும்)."}
ADULT_DECIDES = {"code": "adult_decides",
                 "message": "Your child is 18 or older and decides this for themselves.",
                 "message_ta": "உங்கள் குழந்தை 18 வயது அல்லது அதற்கு மேற்பட்டவர்; இதை அவரே முடிவு செய்வார்."}


def _parents_of(db: Session, student_id: str) -> List[str]:
    return list(db.execute(select(ParentStudent.parent_user_id).where(ParentStudent.student_id == student_id)).scalars())


@router.post("/consent", status_code=status.HTTP_201_CREATED)
def record_consent(req: ConsentIn, current_user: TokenPayload = Depends(require_role(["parent", "student"])), db: Session = Depends(get_db)):
    """S16 DPDP. A parent grants for a minor child only right after signing in with the mobile OTP
    (identity-bound, 15 minutes). A minor asking for an optional purpose creates a request for the parents."""
    if req.purpose not in consent_svc.PURPOSES:
        raise HTTPException(status_code=422, detail=f"Unknown purpose. Use one of: {', '.join(consent_svc.PURPOSES)}")
    student = _subject_for(current_user, db, req.student_id)
    role = normalize_role(current_user.role)
    minor = consent_svc.is_minor(student)
    optional = req.purpose in consent_svc.OPTIONAL
    status_out, method, verified_at = req.status, "in_app", None
    if role == "parent":
        method = "otp_parent"
        if optional and not minor:
            raise HTTPException(status_code=403, detail=ADULT_DECIDES)
        if req.status == "granted" and optional and minor:
            # verifiable parental consent for a minor's optional purpose: OTP sign-in at most 15 minutes ago
            if not consent_svc.identity_fresh(current_user.auth_time):
                raise HTTPException(status_code=403, detail=REAUTH)
        if req.status == "granted" and current_user.auth_time:
            verified_at = datetime.datetime.utcfromtimestamp(current_user.auth_time)
    elif optional and minor and req.status == "granted":
        status_out = "requested"                                    # the parents decide
    row = consent_svc.record(db, college_id=student.college_id, student_id=student.id, granted_by=current_user.sub,
                             purpose=req.purpose, status=status_out, method=method, verified_at=verified_at)
    action = "consent.requested" if status_out == "requested" else "consent.recorded"
    record_audit(db, current_user, action, "student", student.id,
                 {"purpose": req.purpose, "status": status_out, "method": method, "notice_version": row.notice_version,
                  "identity_verified_at": verified_at.isoformat() if verified_at else None})
    if status_out == "requested":
        from core.tenant import get_user_name
        name = get_user_name(db, student.user_id, "Your child")
        for uid in _parents_of(db, student.id):
            notify_user(db, uid, f"{name} asks for your consent", f"For: {req.purpose.replace('_', ' ')}. Open Consent to agree or decline.",
                        title_ta=f"{name} உங்கள் ஒப்புதலைக் கேட்கிறார்", body_ta="ஒப்புதல் பக்கத்தைத் திறந்து ஏற்கவோ மறுக்கவோ செய்யுங்கள்.",
                        kind="approval", link="/parent/consent", college_id=student.college_id)
    db.commit()
    return {"id": row.id, "student_id": student.id, "purpose": row.purpose, "status": row.status, "notice_version": row.notice_version}


def _consent_view(db: Session, student, lang: str) -> dict:
    out = {}
    for p in consent_svc.PURPOSES:
        row = consent_svc.latest(db, student.id, p)
        n = consent_svc.NOTICES.get(p, {})
        out[p] = {"status": row.status if row else None, "effective": consent_svc.allowed(db, student, p),
                  "by_parent": bool(row and row.method in consent_svc.PARENT_METHODS),
                  "needs_parent": p in consent_svc.OPTIONAL and consent_svc.is_minor(student),
                  "notice": n.get("ta" if lang == "ta" else "en"), "notice_version": n.get("version"),
                  "recorded_at": row.recorded_at.isoformat() if row else None}
    return out


@router.get("/consent")
def my_consents(student_id: Optional[str] = None, lang: str = "en",
                current_user: TokenPayload = Depends(require_role(["parent", "student"])), db: Session = Depends(get_db)):
    student = _subject_for(current_user, db, student_id)
    cur = consent_svc.current_for(db, student.college_id, [student.id]).get(student.id, {})
    return {"student_id": student.id, "consents": {p: cur.get(p) for p in consent_svc.PURPOSES},
            "is_minor": consent_svc.is_minor(student), "dob_known": student.date_of_birth is not None,
            "purposes": _consent_view(db, student, lang),
            "identity_fresh": normalize_role(current_user.role) == "parent" and consent_svc.identity_fresh(current_user.auth_time)}


@router.get("/parent/consent")
def parent_consent_overview(lang: str = "en", current_user: TokenPayload = Depends(require_role(["parent"])), db: Session = Depends(get_db)):
    """Every linked child with each purpose, its notice and any request waiting for the parent."""
    from core.tenant import get_parent_children, get_user_name
    children = get_parent_children(current_user, db)
    return {"identity_fresh": consent_svc.identity_fresh(current_user.auth_time),
            "children": [{"student_id": c.id, "name": get_user_name(db, c.user_id, "Student"), "is_minor": consent_svc.is_minor(c),
                          "purposes": _consent_view(db, c, lang)} for c in children]}


class DobIn(BaseModel):
    date_of_birth: datetime.date


@router.put("/college/students/{student_id}/dob")
def set_dob(student_id: str, req: DobIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    """S16 DPDP: the college records the date of birth (it decides who is a minor)."""
    s = db.execute(select(Student).where(Student.id == student_id, Student.college_id == current_user.college_id)).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found in your college")
    today = datetime.date.today()
    if not (datetime.date(1950, 1, 1) <= req.date_of_birth <= today.replace(year=today.year - 10)):
        raise HTTPException(status_code=422, detail="Enter a real date of birth (the student must be at least 10)")
    s.date_of_birth = req.date_of_birth
    record_audit(db, current_user, "student.dob_set", "student", s.id, {"is_minor": consent_svc.is_minor(s)})
    db.commit()
    return {"student_id": s.id, "date_of_birth": s.date_of_birth.isoformat(), "is_minor": consent_svc.is_minor(s)}


@router.get("/admin/consent")
def consent_overview(college_id: str, purpose: Optional[str] = None, page: int = Query(1, ge=1),
                     page_size: int = Query(50, ge=1, le=MAX_PAGE),
                     current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    if purpose and purpose not in consent_svc.PURPOSES:
        raise HTTPException(status_code=422, detail="Unknown purpose")
    require_session(db, current_user, college_id, "consent")
    total = db.execute(select(func.count(Student.id)).where(Student.college_id == college_id)).scalar_one()
    students = db.execute(select(Student, User.name).join(User, User.id == Student.user_id).where(Student.college_id == college_id)
                          .order_by(Student.register_no).offset((page - 1) * page_size).limit(page_size)).all()
    cur = consent_svc.current_for(db, college_id, [s.id for s, _ in students])
    items = []
    for s, name in students:
        c = cur.get(s.id, {})
        items.append({"student_id": s.id, "name": name, "register_no": s.register_no, "batch": s.batch_name,
                      "consents": {p: c.get(p) for p in ([purpose] if purpose else consent_svc.PURPOSES)}})
    db.commit()
    return {"total": total, "page": page, "purposes": list(consent_svc.PURPOSES), "items": items}


@router.get("/admin/consent/{student_id}/history")
def consent_history(student_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found")
    require_session(db, current_user, s.college_id, "consent_history", "student", s.id)
    rows = db.execute(select(ConsentRecord).where(ConsentRecord.subject_student_id == s.id)
                      .order_by(ConsentRecord.recorded_at.desc())).scalars().all()
    db.commit()
    return {"student_id": s.id, "history": [{"purpose": r.purpose, "status": r.status, "method": r.method,
                                              "by": r.granted_by_user_id, "at": r.recorded_at.isoformat()} for r in rows]}


# ---------------------------------------------------------------------------
# Data requests (L27: 02 Settings <-> 48)
# ---------------------------------------------------------------------------

class DataRequestIn(BaseModel):
    student_id: str
    kind: str = Field(pattern="^(export|deletion)$")
    reason: str = Field(min_length=10, max_length=2000)


class DecisionIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


def _may_decide(user: Optional[TokenPayload], r: DataRequest) -> bool:
    """Deletions are approved or rejected by the super admin only; exports by any IREP staff."""
    return user is not None and (r.kind != "deletion" or is_super_admin(user))


def _request_out(r: DataRequest, names: dict, today: datetime.date, user: Optional[TokenPayload] = None) -> dict:
    open_ = r.status in ("received", "in_progress")
    return {"id": r.id, "kind": r.kind, "college_id": r.college_id, "student_id": r.subject_student_id,
            "student_name": names.get(r.subject_student_id), "requested_by": r.requested_by, "reason": r.reason,
            "status": r.status, "due_on": r.due_on.isoformat(), "days_left": (r.due_on - today).days if open_ else None,
            "overdue": open_ and r.due_on < today, "has_export": bool(r.result_ref), "result_summary": r.result_summary,
            "decision_note": r.decision_note, "created_at": r.created_at.isoformat(),
            "can_decide": open_ and _may_decide(user, r) and normalize_role(user.role) in ("irep_admin", "super_admin")}


def _student_names(db: Session, ids) -> dict:
    ids = set(ids) or {"_"}
    return dict(db.execute(select(Student.id, User.name).join(User, User.id == Student.user_id).where(Student.id.in_(ids))).all())


@router.post("/college/data-requests", status_code=status.HTTP_201_CREATED)
def create_data_request(req: DataRequestIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    s = db.execute(select(Student).where(Student.id == req.student_id, Student.college_id == current_user.college_id)).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found in your college")
    open_dup = db.execute(select(DataRequest.id).where(DataRequest.subject_student_id == s.id, DataRequest.kind == req.kind,
                                                       DataRequest.status.in_(("received", "in_progress")))).first()
    if open_dup:
        raise HTTPException(status_code=409, detail="An open request of this kind already exists for this student")
    r = DataRequest(id=f"dr_{uuid.uuid4().hex[:16]}", college_id=s.college_id, kind=req.kind, subject_student_id=s.id,
                    requested_by=current_user.sub, reason=req.reason.strip(), status="received",
                    due_on=datetime.date.today() + datetime.timedelta(days=REQUEST_DAYS))
    db.add(r)
    db.flush()
    record_audit(db, current_user, "data_request.created", "data_request", r.id, {"kind": r.kind, "student_id": s.id})
    # deletions are decided by the super admin; exports by any IREP staff
    roles = ("super_admin",) if r.kind == "deletion" else ("irep_admin", "super_admin")
    for staff_id in db.execute(select(User.id).where(User.role.in_(roles), User.is_active.is_(True))).scalars():
        notify_user(db, staff_id, f"New {r.kind} request", f"Due by {r.due_on.isoformat()}",
                    title_ta="புதிய தரவுக் கோரிக்கை", kind="approval", link="/admin/audit/requests")
    db.commit()
    return _request_out(r, _student_names(db, [s.id]), datetime.date.today())


@router.get("/college/data-requests")
def college_data_requests(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    rows = db.execute(select(DataRequest).where(DataRequest.college_id == current_user.college_id)
                      .order_by(DataRequest.created_at.desc())).scalars().all()
    names = _student_names(db, [r.subject_student_id for r in rows])
    today = datetime.date.today()
    return {"items": [_request_out(r, names, today) for r in rows]}


@router.get("/admin/data-requests")
def staff_queue(status_filter: Optional[str] = Query(None, alias="status"), current_user: TokenPayload = Depends(STAFF),
                db: Session = Depends(get_db)):
    q = select(DataRequest)
    if status_filter:
        q = q.where(DataRequest.status == status_filter)
    open_first = case((DataRequest.status.in_(("received", "in_progress")), 0), else_=1)
    rows = db.execute(q.order_by(open_first, DataRequest.due_on, DataRequest.created_at)).scalars().all()
    open_for = colleges_with_session(db, current_user, {r.college_id for r in rows})
    names = _student_names(db, [r.subject_student_id for r in rows if r.college_id in open_for])
    today = datetime.date.today()
    items = [_request_out(r, names, today, current_user) for r in rows]
    for it in items:
        it["name_hidden"] = it["college_id"] not in open_for       # open a support session to see who it is
    return {"items": items}


def _open_request(db: Session, request_id: str, user: TokenPayload) -> DataRequest:
    r = db.get(DataRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if not _may_decide(user, r):
        raise HTTPException(status_code=403, detail="Only the super admin can approve or reject a deletion request")
    if r.status not in ("received", "in_progress"):
        raise HTTPException(status_code=409, detail=f"This request is already {r.status}")
    return r


def _anonymise(db: Session, s: Student) -> dict:
    """Deletion = anonymise personal fields; aggregates and the audit trail stay."""
    u = db.get(User, s.user_id)
    tag = s.id[-6:]
    if u:
        u.name, u.email, u.phone, u.avatar_initials = f"Deleted student {tag}", f"deleted+{s.id}@invalid", None, "--"
        u.is_active = False
    s.register_no = f"DELETED-{tag}"
    # parent links end: a parent may no longer see a deleted student's records
    links = db.execute(select(ParentStudent).where(ParentStudent.student_id == s.id)).scalars().all()
    for link in links:
        db.delete(link)
    return {"anonymised_fields": ["name", "email", "phone", "register_no"], "parent_links_removed": len(links),
            "kept": ["attendance and score aggregates", "audit trail"]}


@router.post("/admin/data-requests/{request_id}/complete")
def complete_request(request_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    r = _open_request(db, request_id, current_user)
    s = db.get(Student, r.subject_student_id)
    now = datetime.datetime.utcnow()
    r.decided_by, r.decided_at = current_user.sub, now
    if r.kind == "export":
        r.status = "in_progress"           # the outbox builds the file after commit, then completes it
        emit(db, "data_request.build_export", {"request_id": r.id}, college_id=r.college_id, entity_type="data_request", entity_id=r.id)
        record_audit(db, current_user, "data_request.export_started", "data_request", r.id, {"student_id": r.subject_student_id},
                     college_id=r.college_id)
    else:
        r.result_summary = _anonymise(db, s)
        r.status = "completed"
        record_audit(db, current_user, "data_request.completed", "data_request", r.id, r.result_summary, college_id=r.college_id)
        notify_user(db, r.requested_by, "Deletion request completed", "The student's personal data was anonymised.",
                    title_ta="நீக்கக் கோரிக்கை முடிந்தது", kind="approval", link="/college/settings", college_id=r.college_id)
    db.commit()
    return {"id": r.id, "status": r.status}


@router.post("/admin/data-requests/{request_id}/reject")
def reject_request(request_id: str, req: DecisionIn, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    r = _open_request(db, request_id, current_user)
    r.status, r.decision_note, r.decided_by, r.decided_at = "rejected", req.reason.strip(), current_user.sub, datetime.datetime.utcnow()
    record_audit(db, current_user, "data_request.rejected", "data_request", r.id, {"reason": r.decision_note}, college_id=r.college_id)
    notify_user(db, r.requested_by, f"{r.kind.capitalize()} request rejected", r.decision_note,
                title_ta="தரவுக் கோரிக்கை நிராகரிக்கப்பட்டது", kind="approval", link="/college/settings", college_id=r.college_id)
    db.commit()
    return {"id": r.id, "status": r.status}


def _export_payload(db: Session, s: Student) -> dict:
    u = db.get(User, s.user_id)
    attendance = db.execute(select(SessionAttendance).where(SessionAttendance.student_id == s.id)).scalars().all()
    subs = db.execute(select(CodingSubmission).where(CodingSubmission.student_id == s.id)).scalars().all()
    attempts = db.execute(select(TestAttempt).where(TestAttempt.student_id == s.id)).scalars().all()
    certs = db.execute(select(Certificate).where(Certificate.student_id == s.id)).scalars().all()
    consents = db.execute(select(ConsentRecord).where(ConsentRecord.subject_student_id == s.id)).scalars().all()
    iso = lambda d: d.isoformat() if d else None
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "profile": {"name": u.name if u else None, "email": u.email if u else None, "phone": u.phone if u else None,
                    "register_no": s.register_no, "branch": s.branch, "semester": s.semester, "batch": s.batch_name,
                    "language": u.language_pref if u else None},
        "readiness": {"score": s.readiness_score, "band": s.readiness_band, "attendance_pct": s.attendance_pct,
                      "problems_solved": s.problems_solved},
        "attendance": [{"session_id": a.session_id, "status": a.status, "minutes_present": a.minutes_present,
                        "marked_at": iso(a.marked_at)} for a in attendance],
        "coding_submissions": [{"problem_id": c.problem_id, "language": c.language, "status": c.status,
                                "tests_passed": c.tests_passed, "tests_total": c.tests_total, "at": iso(c.created_at)} for c in subs],
        "test_attempts": [{"test_id": t.test_id, "status": t.status, "score": getattr(t, "score", None),
                           "started_at": iso(t.started_at)} for t in attempts],
        "certificates": [{"title": getattr(c, "title", None), "status": c.status} for c in certs],
        "consents": [{"purpose": c.purpose, "status": c.status, "method": c.method, "at": iso(c.recorded_at)} for c in consents],
    }


@outbox_handler("data_request.build_export")
def _build_export(db: Session, event) -> None:
    r = db.get(DataRequest, event.payload["request_id"])
    if r is None or r.status == "completed":
        return                                               # idempotent
    s = db.get(Student, r.subject_student_id)
    key = f"exports/{r.college_id}/{r.id}.json"
    get_storage().put(key, json.dumps(_export_payload(db, s), ensure_ascii=False, indent=2).encode("utf-8"))
    r.result_ref, r.status = key, "completed"
    r.result_summary = {"file": "json", "sections": ["profile", "readiness", "attendance", "coding_submissions", "test_attempts", "certificates", "consents"]}
    record_audit(db, None, "data_request.completed", "data_request", r.id, {"kind": "export"}, college_id=r.college_id)
    notify_user(db, r.requested_by, "Data export ready", "Download it from College settings > Data requests.",
                title_ta="தரவு ஏற்றுமதி தயார்", kind="approval", link="/college/settings", college_id=r.college_id)


def _download(db: Session, r: DataRequest, user: TokenPayload) -> Response:
    if not r.result_ref:
        raise HTTPException(status_code=409, detail="The export is not ready yet")
    data = get_storage().get(r.result_ref)
    record_audit(db, user, "data_request.downloaded", "data_request", r.id, None, college_id=r.college_id)
    db.commit()
    return Response(content=data, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="irep-export-{r.subject_student_id}.json"'})


@router.get("/admin/data-requests/{request_id}/export")
def staff_download(request_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    r = db.get(DataRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    require_session(db, current_user, r.college_id, "data_export", "data_request", r.id)
    return _download(db, r, current_user)


@router.get("/college/data-requests/{request_id}/export")
def college_download(request_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    r = db.execute(select(DataRequest).where(DataRequest.id == request_id, DataRequest.college_id == current_user.college_id)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return _download(db, r, current_user)


# ---------------------------------------------------------------- S16 DPDP: self-service requests

class SelfRequestIn(BaseModel):
    kind: str = Field(pattern="^(export|deletion)$")
    reason: str = Field(min_length=10, max_length=2000)
    student_id: Optional[str] = None                 # a parent names the child


ASK_PARENT = {"code": "ask_parent",
              "message": "You are under 18, so a parent makes this request for you from the parent's Consent page.",
              "message_ta": "நீங்கள் 18 வயதுக்குக் குறைவானவர்; பெற்றோர் தங்கள் ஒப்புதல் பக்கத்திலிருந்து இந்தக் கோரிக்கையைச் செய்வார்."}


@router.post("/me/data-requests", status_code=status.HTTP_201_CREATED)
def self_service_request(req: SelfRequestIn, current_user: TokenPayload = Depends(require_role(["parent", "student"])),
                         db: Session = Depends(get_db)):
    """A parent (for a linked child) or an adult student (for themselves) asks for a copy or deletion."""
    role = normalize_role(current_user.role)
    s = _subject_for(current_user, db, req.student_id)
    if role == "student" and consent_svc.is_minor(s):
        raise HTTPException(status_code=403, detail=ASK_PARENT)
    open_dup = db.execute(select(DataRequest.id).where(DataRequest.subject_student_id == s.id, DataRequest.kind == req.kind,
                                                       DataRequest.status.in_(("received", "in_progress")))).first()
    if open_dup:
        raise HTTPException(status_code=409, detail="An open request of this kind already exists for this student")
    r = DataRequest(id=f"dr_{uuid.uuid4().hex[:16]}", college_id=s.college_id, kind=req.kind, subject_student_id=s.id,
                    requested_by=current_user.sub, reason=req.reason.strip(), status="received",
                    due_on=datetime.date.today() + datetime.timedelta(days=REQUEST_DAYS))
    db.add(r)
    db.flush()
    record_audit(db, current_user, "data_request.created", "data_request", r.id, {"kind": r.kind, "self_service": role})
    roles = ("super_admin",) if r.kind == "deletion" else ("irep_admin", "super_admin")
    for uid in db.execute(select(User.id).where(User.role.in_(roles), User.is_active.is_(True))).scalars():
        notify_user(db, uid, f"New {r.kind} request (from a {role})", f"Due by {r.due_on.isoformat()}",
                    title_ta="புதிய தரவுக் கோரிக்கை", kind="approval", link="/admin/audit/requests")
    for uid in db.execute(select(User.id).where(User.college_id == s.college_id, User.role == "college_admin",
                                                User.is_active.is_(True))).scalars():
        notify_user(db, uid, f"A {role} asked for a data {r.kind}", f"Due by {r.due_on.isoformat()}",
                    title_ta="தரவுக் கோரிக்கை பெறப்பட்டது", kind="approval", link="/college/settings", college_id=s.college_id)
    db.commit()
    return {"id": r.id, "kind": r.kind, "status": r.status, "due_on": r.due_on.isoformat(), "student_id": s.id}


@router.get("/me/data-requests")
def my_data_requests(current_user: TokenPayload = Depends(require_role(["parent", "student"])), db: Session = Depends(get_db)):
    rows = db.execute(select(DataRequest).where(DataRequest.requested_by == current_user.sub)
                      .order_by(DataRequest.created_at.desc())).scalars().all()
    return {"items": [{"id": r.id, "kind": r.kind, "student_id": r.subject_student_id, "status": r.status,
                       "due_on": r.due_on.isoformat(), "has_export": bool(r.result_ref), "decision_note": r.decision_note,
                       "created_at": r.created_at.isoformat()} for r in rows]}


@router.get("/me/data-requests/{request_id}/export")
def my_export(request_id: str, current_user: TokenPayload = Depends(require_role(["parent", "student"])), db: Session = Depends(get_db)):
    r = db.get(DataRequest, request_id)
    if r is None or r.requested_by != current_user.sub or r.kind != "export":
        raise HTTPException(status_code=404, detail="Request not found")
    return _download(db, r, current_user)
