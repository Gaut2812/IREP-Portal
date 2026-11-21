"""Screens 26 (student), 27 (parent), 28 (college) certificates and the 43 proof decision.
Links L10 (26 ↔ 43), L32 (26 → 27), L35 (→ 28 aggregates). Release rule 5.1.4: an external
certificate shows as verified only after the trainer approves the proof.
Spec: docs/screens/26-27-28-certificates.md"""
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_child_for_parent, get_student_for_user, get_trainer_batch_ids, get_trainer_for_user, get_user_name
from models.schema import Batch, BatchTrainer, Certificate, ParentStudent, Student, Trainer
from services.audit import record_audit
from services.consent import is_granted
from services.notifications import notify_user
from services.storage import get_storage

router = APIRouter(tags=["Certificates"])
STUDENT, TRAINER, PARENT = require_role(["student"]), require_role(["trainer"]), require_role(["parent"])
COLLEGE = require_role(["college_admin", "placement_officer"])
MAX_BYTES = 5 * 1024 * 1024
SIGNATURES = {b"%PDF": ("application/pdf", "pdf"), b"\x89PNG": ("image/png", "png"), b"\xff\xd8\xff": ("image/jpeg", "jpg")}
STATUS_TA = {"earned": "சரிபார்க்கப்பட்டது", "scheduled": "திட்டமிடப்பட்டது", "pending_proof": "சரிபார்ப்பில்", "rejected": "நிராகரிக்கப்பட்டது"}


class DecisionIn(BaseModel):
    decision: str
    note: Optional[str] = Field(default=None, max_length=500)


def _sniff(data: bytes) -> tuple:
    for sig, kind in SIGNATURES.items():
        if data.startswith(sig):
            return kind
    raise HTTPException(status_code=422, detail="Upload a PDF, PNG or JPEG file")


def _out(c: Certificate, lang: str = "en", with_proof: bool = True) -> dict:
    return {"id": c.id, "title": c.title, "issuer": c.issuer, "type": c.cert_type, "status": c.status,
            "status_label": STATUS_TA.get(c.status, c.status) if lang == "ta" else c.status.replace("_", " ").capitalize(),
            "verified": c.status == "earned", "issued_on": c.issued_on.isoformat() if c.issued_on else None,
            "exam_date": c.exam_date.isoformat() if c.exam_date else None, "verify_code": c.verify_code,
            "credential_id": c.credential_id, "has_proof": bool(c.proof_key) if with_proof else None,
            "proof_submitted_at": c.proof_submitted_at.isoformat() if c.proof_submitted_at else None,
            "decision_note": c.decision_note if c.status == "rejected" else None, "voucher": bool(c.voucher_code)}


def _batch_trainer_users(db: Session, batch_id: Optional[str]) -> list:
    return db.execute(select(Trainer.user_id).join(BatchTrainer, BatchTrainer.trainer_id == Trainer.id)
                      .where(BatchTrainer.batch_id == batch_id)).scalars().all()


def _store_proof(db: Session, c: Certificate, st: Student, file: UploadFile, data: bytes, user: TokenPayload) -> None:
    mime, ext = _sniff(data)
    key = f"certificates/{st.college_id}/{st.id}/{c.id}-{uuid.uuid4().hex[:8]}.{ext}"
    get_storage().put(key, data)
    c.proof_key, c.proof_filename = key, (file.filename or f"proof.{ext}")[:255]
    c.proof_submitted_at, c.status, c.decision_note = datetime.datetime.utcnow(), "pending_proof", None
    record_audit(db, user, "certificate_proof.submitted", "certificate", c.id, {"title": c.title, "bytes": len(data), "type": mime})
    name = get_user_name(db, st.user_id, "A student")
    for uid in _batch_trainer_users(db, st.batch_id):
        notify_user(db, uid, f"Certificate proof to check: {name}", c.title, title_ta=f"சரிபார்க்க வேண்டிய சான்றிதழ்: {name}",
                    kind="approval", link="/trainer/approvals", college_id=st.college_id)


# ------------------------------------------------------------------ Screen 26 (student)

@router.get("/student/certificates")
def my_certificates(lang: str = "en", current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    st = get_student_for_user(current_user, db)
    certs = db.execute(select(Certificate).where(Certificate.student_id == st.id, Certificate.college_id == st.college_id)
                       .order_by(Certificate.issued_on.desc().nullsfirst(), Certificate.created_at.desc())).scalars().all()
    rows = [_out(c, lang) for c in certs]
    return {"certificates": rows, "counts": {k: sum(1 for r in rows if r["status"] == k) for k in ("earned", "scheduled", "pending_proof", "rejected")}}


@router.post("/student/certificates", status_code=status.HTTP_201_CREATED)
async def add_external(title: str = Form(..., min_length=3, max_length=255), issuer: str = Form(..., min_length=2, max_length=128),
                       issued_on: datetime.date = Form(...), credential_id: Optional[str] = Form(None, max_length=128),
                       file: UploadFile = File(...), current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    """An external certificate with its proof; pending until the trainer approves it (L10)."""
    if issued_on > datetime.date.today():
        raise HTTPException(status_code=422, detail="The issue date cannot be in the future")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 5 MB")
    st = get_student_for_user(current_user, db)
    c = Certificate(id=f"cert_{uuid.uuid4().hex[:14]}", college_id=st.college_id, student_id=st.id, title=title.strip(),
                    issuer=issuer.strip(), cert_type="external", issued_on=issued_on, credential_id=(credential_id or "").strip() or None)
    db.add(c)
    _store_proof(db, c, st, file, data, current_user)
    db.commit()
    return _out(c)


@router.post("/student/certificates/{cert_id}/proof")
async def add_proof(cert_id: str, file: UploadFile = File(...), credential_id: Optional[str] = Form(None, max_length=128),
                    current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    """Proof for a scheduled exam, or a new proof after a rejection."""
    st = get_student_for_user(current_user, db)
    c = db.execute(select(Certificate).where(Certificate.id == cert_id, Certificate.student_id == st.id)).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if c.status not in ("scheduled", "rejected"):
        raise HTTPException(status_code=409, detail="This certificate does not need a proof now")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="The file is larger than 5 MB")
    if credential_id:
        c.credential_id = credential_id.strip()
    if c.status == "scheduled":
        c.issued_on = datetime.date.today()
    _store_proof(db, c, st, file, data, current_user)
    db.commit()
    return _out(c)


@router.get("/student/certificates/{cert_id}/proof")
def my_proof(cert_id: str, current_user: TokenPayload = Depends(STUDENT), db: Session = Depends(get_db)):
    st = get_student_for_user(current_user, db)
    c = db.execute(select(Certificate).where(Certificate.id == cert_id, Certificate.student_id == st.id)).scalar_one_or_none()
    if c is None or not c.proof_key:
        raise HTTPException(status_code=404, detail="Proof not found")
    return _file(c)


def _file(c: Certificate) -> Response:
    data = get_storage().get(c.proof_key)
    mime = _sniff(data)[0]
    return Response(content=data, media_type=mime, headers={"Content-Disposition": f'inline; filename="{c.id}.{_sniff(data)[1]}"',
                                                            "X-Content-Type-Options": "nosniff"})


# ------------------------------------------------------------------ Screen 43 (trainer decides, L10)

def _trainer_cert(db: Session, cert_id: str, user: TokenPayload) -> tuple:
    batch_ids = set(get_trainer_batch_ids(get_trainer_for_user(user, db), db))
    c = db.execute(select(Certificate).where(Certificate.id == cert_id, Certificate.college_id == user.college_id)).scalar_one_or_none()
    st = db.get(Student, c.student_id) if c else None
    if c is None or st is None or st.batch_id not in batch_ids:
        raise HTTPException(status_code=404, detail="Certificate not found in your batches")
    return c, st


@router.get("/trainer/certificates/{cert_id}/proof")
def trainer_proof(cert_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    c, st = _trainer_cert(db, cert_id, current_user)
    if not c.proof_key:
        raise HTTPException(status_code=404, detail="No proof uploaded")
    record_audit(db, current_user, "certificate_proof.viewed", "certificate", c.id, {"student_id": st.id})     # sensitive read
    db.commit()
    return _file(c)


@router.post("/trainer/approvals/certificates/{cert_id}")
def decide(cert_id: str, req: DecisionIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    c, st = _trainer_cert(db, cert_id, current_user)
    if c.status != "pending_proof":
        raise HTTPException(status_code=409, detail=f"This certificate is {c.status}, not waiting for a decision")
    if req.decision not in ("approve", "deny"):
        raise HTTPException(status_code=422, detail="decision must be approve or deny")
    note = (req.note or "").strip() or None
    if req.decision == "deny" and not note:
        raise HTTPException(status_code=422, detail="Tell the student what to fix when you reject a proof")
    trainer = get_trainer_for_user(current_user, db)
    c.status = "earned" if req.decision == "approve" else "rejected"
    c.decided_by, c.decided_at, c.decision_note = trainer.id, datetime.datetime.utcnow(), note
    if c.status == "earned" and not c.verify_code:
        c.verify_code = f"IREP-X-{c.id[-10:].upper()}"
    record_audit(db, current_user, "certificate_proof.decided", "certificate", c.id, {"student_id": st.id, "decision": c.status})
    if c.status == "earned":
        notify_user(db, st.user_id, f"Certificate verified: {c.title}", "It now shows as verified on your profile.",
                    title_ta=f"சான்றிதழ் சரிபார்க்கப்பட்டது: {c.title}", kind="approval", link="/student/certificates", college_id=c.college_id)
        name = get_user_name(db, st.user_id, "your child")
        for pid in db.execute(select(ParentStudent.parent_user_id).where(ParentStudent.student_id == st.id)).scalars():   # L32
            notify_user(db, pid, f"{name} earned a certificate: {c.title}", c.issuer, title_ta=f"{name} சான்றிதழ் பெற்றார்: {c.title}",
                        kind="info", link="/parent/certificates", college_id=c.college_id)
    else:
        notify_user(db, st.user_id, f"Proof not accepted: {c.title}", note, title_ta=f"ஆதாரம் ஏற்கப்படவில்லை: {c.title}",
                    kind="approval", link="/student/certificates", college_id=c.college_id)
    db.commit()
    return _out(c)


# ------------------------------------------------------------------ Screen 27 (parent, L32)

@router.get("/parent/certificates")
def child_certificates(child_id: Optional[str] = None, lang: str = "en", current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    child = get_child_for_parent(current_user, db, child_id)
    name = get_user_name(db, child.user_id, "Student")
    if not is_granted(db, child.id, "parent_data_processing"):
        return {"consent_required": True, "ward": {"id": child.id, "name": name}, "earned": [], "upcoming": []}
    certs = db.execute(select(Certificate).where(Certificate.student_id == child.id, Certificate.college_id == child.college_id,
                                                 Certificate.status.in_(["earned", "scheduled"]))
                       .order_by(Certificate.issued_on.desc())).scalars().all()
    # read-only copy: no proof files, no rejected or pending items (verified only after approval)
    return {"consent_required": False, "ward": {"id": child.id, "name": name},
            "earned": [_out(c, lang, with_proof=False) for c in certs if c.status == "earned"],
            "upcoming": [_out(c, lang, with_proof=False) for c in certs if c.status == "scheduled"]}


# ------------------------------------------------------------------ Screen 28 (college, L35 aggregates)

@router.get("/college/certifications")
def college_certifications(months: int = Query(6, ge=1, le=24), current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    """Counts only: no names, files or notes."""
    cid = current_user.college_id
    base = select(Certificate).where(Certificate.college_id == cid)
    by_status = dict(db.execute(select(Certificate.status, func.count(Certificate.id)).where(Certificate.college_id == cid)
                                .group_by(Certificate.status)).all())
    since = (datetime.date.today().replace(day=1) - datetime.timedelta(days=31 * (months - 1))).replace(day=1)
    monthly = {}
    for d in db.execute(select(Certificate.issued_on).where(Certificate.college_id == cid, Certificate.status == "earned",
                                                            Certificate.issued_on >= since)).scalars():
        monthly[d.strftime("%Y-%m")] = monthly.get(d.strftime("%Y-%m"), 0) + 1
    issuers = db.execute(select(Certificate.issuer, func.count(Certificate.id)).where(Certificate.college_id == cid, Certificate.status == "earned")
                         .group_by(Certificate.issuer).order_by(func.count(Certificate.id).desc()).limit(8)).all()
    batches = db.execute(select(Batch.name, func.count(Certificate.id), func.count(func.distinct(Certificate.student_id)))
                         .join(Student, Student.id == Certificate.student_id).join(Batch, Batch.id == Student.batch_id)
                         .where(Certificate.college_id == cid, Certificate.status == "earned").group_by(Batch.name).order_by(Batch.name)).all()
    vouchers = db.execute(select(Certificate.status, func.count(Certificate.id)).where(Certificate.college_id == cid,
                                                                                       Certificate.voucher_code.is_not(None))
                          .group_by(Certificate.status)).all()
    v = dict(vouchers)
    students = db.execute(select(func.count(Student.id)).where(Student.college_id == cid)).scalar_one()
    holders = db.execute(select(func.count(func.distinct(Certificate.student_id))).where(Certificate.college_id == cid,
                                                                                         Certificate.status == "earned")).scalar_one()
    return {
        "totals": {"earned": by_status.get("earned", 0), "scheduled_exams": by_status.get("scheduled", 0),
                   "proofs_pending": by_status.get("pending_proof", 0), "proofs_rejected": by_status.get("rejected", 0),
                   "students_with_certificate_pct": round(100 * holders / students) if students else 0},
        "monthly": [{"month": k, "earned": monthly[k]} for k in sorted(monthly)],
        "issuers": [{"issuer": i, "earned": n} for i, n in issuers],
        "batches": [{"batch": b, "earned": n, "students": s} for b, n, s in batches],
        "vouchers": {"issued": sum(v.values()), "used": v.get("earned", 0) + v.get("pending_proof", 0), "unused": v.get("scheduled", 0)},
    }
