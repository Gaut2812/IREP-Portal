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
from core.security import TokenPayload, normalize_role, require_role
from core.tenant import get_child_for_parent, get_student_for_user
from models.schema import (AuditLog, CodingSubmission, ConsentRecord, DataRequest, ParentStudent,
                           SessionAttendance, Student, TestAttempt, User, Certificate)
from services import consent as consent_svc
from services.audit import record_audit
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


@router.post("/consent", status_code=status.HTTP_201_CREATED)
def record_consent(req: ConsentIn, current_user: TokenPayload = Depends(require_role(["parent", "student"])), db: Session = Depends(get_db)):
    if req.purpose not in consent_svc.PURPOSES:
        raise HTTPException(status_code=422, detail=f"Unknown purpose. Use one of: {', '.join(consent_svc.PURPOSES)}")
    student = _subject_for(current_user, db, req.student_id)
    method = "otp_parent" if normalize_role(current_user.role) == "parent" else "in_app"
    row = consent_svc.record(db, college_id=student.college_id, student_id=student.id, granted_by=current_user.sub,
                             purpose=req.purpose, status=req.status, method=method)
    record_audit(db, current_user, "consent.recorded", "student", student.id, {"purpose": req.purpose, "status": req.status, "method": method})
    db.commit()
    return {"id": row.id, "student_id": student.id, "purpose": row.purpose, "status": row.status}


@router.get("/consent")
def my_consents(student_id: Optional[str] = None, current_user: TokenPayload = Depends(require_role(["parent", "student"])),
                db: Session = Depends(get_db)):
    student = _subject_for(current_user, db, student_id)
    cur = consent_svc.current_for(db, student.college_id, [student.id]).get(student.id, {})
    return {"student_id": student.id, "consents": {p: cur.get(p) for p in consent_svc.PURPOSES}}


@router.get("/admin/consent")
def consent_overview(college_id: str, purpose: Optional[str] = None, page: int = Query(1, ge=1),
                     page_size: int = Query(50, ge=1, le=MAX_PAGE),
                     current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    if purpose and purpose not in consent_svc.PURPOSES:
        raise HTTPException(status_code=422, detail="Unknown purpose")
    total = db.execute(select(func.count(Student.id)).where(Student.college_id == college_id)).scalar_one()
    students = db.execute(select(Student, User.name).join(User, User.id == Student.user_id).where(Student.college_id == college_id)
                          .order_by(Student.register_no).offset((page - 1) * page_size).limit(page_size)).all()
    cur = consent_svc.current_for(db, college_id, [s.id for s, _ in students])
    items = []
    for s, name in students:
        c = cur.get(s.id, {})
        items.append({"student_id": s.id, "name": name, "register_no": s.register_no, "batch": s.batch_name,
                      "consents": {p: c.get(p) for p in ([purpose] if purpose else consent_svc.PURPOSES)}})
    _support_access(db, current_user, college_id, "consent")
    db.commit()
    return {"total": total, "page": page, "purposes": list(consent_svc.PURPOSES), "items": items}


@router.get("/admin/consent/{student_id}/history")
def consent_history(student_id: str, current_user: TokenPayload = Depends(STAFF), db: Session = Depends(get_db)):
    s = db.get(Student, student_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Student not found")
    rows = db.execute(select(ConsentRecord).where(ConsentRecord.subject_student_id == s.id)
                      .order_by(ConsentRecord.recorded_at.desc())).scalars().all()
    _support_access(db, current_user, s.college_id, "consent_history")
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


def _request_out(r: DataRequest, names: dict, today: datetime.date) -> dict:
    open_ = r.status in ("received", "in_progress")
    return {"id": r.id, "kind": r.kind, "college_id": r.college_id, "student_id": r.subject_student_id,
            "student_name": names.get(r.subject_student_id), "requested_by": r.requested_by, "reason": r.reason,
            "status": r.status, "due_on": r.due_on.isoformat(), "days_left": (r.due_on - today).days if open_ else None,
            "overdue": open_ and r.due_on < today, "has_export": bool(r.result_ref), "result_summary": r.result_summary,
            "decision_note": r.decision_note, "created_at": r.created_at.isoformat()}


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
    for staff_id in db.execute(select(User.id).where(User.role == "irep_admin", User.is_active.is_(True))).scalars():
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
    names = _student_names(db, [r.subject_student_id for r in rows])
    today = datetime.date.today()
    return {"items": [_request_out(r, names, today) for r in rows]}


def _open_request(db: Session, request_id: str) -> DataRequest:
    r = db.get(DataRequest, request_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
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
    r = _open_request(db, request_id)
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
    r = _open_request(db, request_id)
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
    return _download(db, r, current_user)


@router.get("/college/data-requests/{request_id}/export")
def college_download(request_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    r = db.execute(select(DataRequest).where(DataRequest.id == request_id, DataRequest.college_id == current_user.college_id)).scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return _download(db, r, current_user)
