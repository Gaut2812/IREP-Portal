"""Screen 03 · Branches and batches (college admin). Spec: docs/screens/03-branches-and-batches.md

Structure, student import (CSV, dry run first), trainer mapping and semester
promotion. Everything is scoped to the college in the caller's token.
"""
import csv
import io
import re
import secrets
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, get_password_hash, keycloak_mode, require_role
from models.schema import Batch, BatchTrainer, Branch, ParentStudent, Student, Trainer, User
from services.audit import record_audit
from services import consent as consent_svc
from services.antivirus import check_upload
from services.outbox import emit

router = APIRouter(prefix="/college", tags=["Screen 03 · Branches and batches"])
COLLEGE = require_role(["college_admin"])
MAX_ROWS = 5000
CSV_COLUMNS = ["register_no", "name", "email", "phone", "branch_code", "batch", "semester", "parent_name", "parent_phone",
               "parent_email", "parent_consent", "parent_consent_ref"]
CONSENT_YES = ("yes", "y", "true", "1", "granted")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---- payloads ----
class BranchIn(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    code: str = Field(min_length=2, max_length=16, pattern=r"^[A-Za-z0-9&]+$")
    track: str = Field(default="Software Engineering", max_length=64)
    hod_name: Optional[str] = Field(default=None, max_length=128)


class BatchIn(BaseModel):
    branch_id: str
    short_name: str = Field(min_length=2, max_length=32)
    semester: int = Field(ge=2, le=7)
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    track: str = Field(default="Software Engineering", max_length=64)


class TrainerMapIn(BaseModel):
    trainer_id: str
    role: str = Field(default="primary", pattern="^(primary|substitute)$")


# ---- helpers ----
def _branch(db: Session, college_id: str, branch_id: str) -> Branch:
    b = db.execute(select(Branch).where(Branch.id == branch_id, Branch.college_id == college_id)).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Branch not found")
    return b


def _batch(db: Session, college_id: str, batch_id: str) -> Batch:
    b = db.execute(select(Batch).where(Batch.id == batch_id, Batch.college_id == college_id)).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    return b


def _trainer_names(db: Session, college_id: str) -> Dict[str, str]:
    return dict(db.execute(select(Trainer.id, User.name).join(User, User.id == Trainer.user_id)
                           .where(Trainer.college_id == college_id)).all())


def _norm_phone(raw: str) -> Optional[str]:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if len(digits) == 10 else None


def _initials(name: str) -> str:
    return "".join(p[0] for p in name.split()[:2]).upper() or "ST"


# ---- structure ----
@router.get("/structure")
def get_structure(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid = current_user.college_id
    branches = db.execute(select(Branch).where(Branch.college_id == cid).order_by(Branch.name)).scalars().all()
    batches = db.execute(select(Batch).where(Batch.college_id == cid).order_by(Batch.semester, Batch.short_name)).scalars().all()
    counts = dict(db.execute(select(Student.batch_id, func.count(Student.id)).where(Student.college_id == cid)
                             .group_by(Student.batch_id)).all())
    names = _trainer_names(db, cid)
    maps: Dict[str, List[dict]] = {}
    for m in db.execute(select(BatchTrainer).where(BatchTrainer.college_id == cid)).scalars():
        maps.setdefault(m.batch_id, []).append({"trainer_id": m.trainer_id, "name": names.get(m.trainer_id, m.trainer_id), "role": m.role})
    return {
        "students_total": sum(counts.values()),
        "unassigned_students": counts.get(None, 0),
        "branches": [{
            "id": b.id, "name": b.name, "code": b.code, "track": b.track, "hod_name": b.hod_name,
            "batches": [{"id": x.id, "short_name": x.short_name, "name": x.name, "semester": x.semester, "academic_year": x.academic_year,
                         "track": x.track, "students": counts.get(x.id, 0), "trainers": maps.get(x.id, [])}
                        for x in batches if x.branch_id == b.id],
        } for b in branches],
    }


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def create_branch(req: BranchIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid, code = current_user.college_id, req.code.strip().upper()
    if db.execute(select(Branch.id).where(Branch.college_id == cid, func.upper(Branch.code) == code)).first():
        raise HTTPException(status_code=409, detail=f"Branch code {code} already exists in your college")
    b = Branch(id=f"br_{uuid.uuid4().hex[:16]}", college_id=cid, name=req.name.strip(), code=code, track=req.track.strip(),
               hod_name=(req.hod_name or "").strip() or None)
    db.add(b)
    db.flush()
    record_audit(db, current_user, "structure.branch_created", "branch", b.id, {"code": code})
    db.commit()
    return {"id": b.id, "code": b.code}


@router.post("/batches", status_code=status.HTTP_201_CREATED)
def create_batch(req: BatchIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid = current_user.college_id
    br = _branch(db, cid, req.branch_id)
    short = req.short_name.strip()
    dup = db.execute(select(Batch.id).where(Batch.college_id == cid, Batch.branch_id == br.id, Batch.short_name == short,
                                            Batch.semester == req.semester, Batch.academic_year == req.academic_year)).first()
    if dup:
        raise HTTPException(status_code=409, detail=f"Batch {short} already exists for semester {req.semester}, {req.academic_year}")
    b = Batch(id=f"bat_{uuid.uuid4().hex[:16]}", college_id=cid, branch_id=br.id, short_name=short, name=f"{short} · Sem {req.semester}",
              semester=req.semester, academic_year=req.academic_year, track=req.track.strip(), is_active=True)
    db.add(b)
    db.flush()
    record_audit(db, current_user, "structure.batch_created", "batch", b.id, {"short_name": short, "semester": req.semester})
    db.commit()
    return {"id": b.id, "name": b.name}


@router.get("/trainers")
def list_trainers(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    rows = db.execute(select(Trainer.id, User.name, User.email, Trainer.specialization).join(User, User.id == Trainer.user_id)
                      .where(Trainer.college_id == current_user.college_id).order_by(User.name)).all()
    return {"trainers": [{"id": r[0], "name": r[1], "email": r[2], "specialization": r[3]} for r in rows]}


@router.post("/batches/{batch_id}/trainers", status_code=status.HTTP_201_CREATED)
def map_trainer(batch_id: str, req: TrainerMapIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid = current_user.college_id
    b = _batch(db, cid, batch_id)
    t = db.execute(select(Trainer).where(Trainer.id == req.trainer_id, Trainer.college_id == cid)).scalar_one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="Trainer not found in your college")
    existing = db.execute(select(BatchTrainer).where(BatchTrainer.batch_id == b.id, BatchTrainer.trainer_id == t.id)).scalar_one_or_none()
    if req.role == "primary":
        other = db.execute(select(BatchTrainer).where(BatchTrainer.batch_id == b.id, BatchTrainer.role == "primary",
                                                      BatchTrainer.trainer_id != t.id)).scalar_one_or_none()
        if other:
            raise HTTPException(status_code=409, detail="This batch already has a primary trainer. Map this trainer as a substitute or unmap the primary first.")
    if existing:
        existing.role = req.role
    else:
        db.add(BatchTrainer(id=f"bt_{uuid.uuid4().hex[:16]}", college_id=cid, batch_id=b.id, trainer_id=t.id, role=req.role))
    record_audit(db, current_user, "structure.trainer_mapped", "batch", b.id, {"trainer_id": t.id, "role": req.role})
    db.commit()
    return {"batch_id": b.id, "trainer_id": t.id, "role": req.role}


@router.delete("/batches/{batch_id}/trainers/{trainer_id}")
def unmap_trainer(batch_id: str, trainer_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    b = _batch(db, current_user.college_id, batch_id)
    m = db.execute(select(BatchTrainer).where(BatchTrainer.batch_id == b.id, BatchTrainer.trainer_id == trainer_id)).scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="This trainer is not mapped to the batch")
    db.delete(m)
    record_audit(db, current_user, "structure.trainer_unmapped", "batch", b.id, {"trainer_id": trainer_id})
    db.commit()
    return {"success": True}


@router.post("/batches/{batch_id}/promote")
def promote_batch(batch_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    b = _batch(db, current_user.college_id, batch_id)
    if b.semester >= 7:
        raise HTTPException(status_code=409, detail="Semester 7 is the last IREP semester")
    b.semester += 1
    b.name = f"{b.short_name} · Sem {b.semester}"
    students = db.execute(select(Student).where(Student.batch_id == b.id, Student.college_id == b.college_id)).scalars().all()
    for s in students:
        s.semester, s.batch_name = b.semester, b.name
    record_audit(db, current_user, "batch.promoted", "batch", b.id, {"to_semester": b.semester, "students": len(students)})
    db.commit()
    return {"batch_id": b.id, "semester": b.semester, "students": len(students)}


# ---- student import ----
def _parse_csv(raw: bytes) -> List[dict]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="The file must be UTF-8 CSV")
    reader = csv.DictReader(io.StringIO(text))
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    missing = [c for c in CSV_COLUMNS[:7] if c not in header]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing columns: {', '.join(missing)}. Expected: {','.join(CSV_COLUMNS)}")
    rows = []
    for row in reader:
        rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in row.items()})
        if len(rows) > MAX_ROWS:
            raise HTTPException(status_code=422, detail=f"At most {MAX_ROWS} rows per file")
    return rows


def _find_parent(db: Session, cid: str, phone: str, email: Optional[str]) -> Optional[User]:
    """Tenant-scoped: a parent in another college is a different account."""
    found = db.execute(select(User).where(User.college_id == cid, User.role == "parent", User.phone == phone)).scalars().first()
    if found is None and email:
        found = db.execute(select(User).where(User.college_id == cid, User.role == "parent",
                                              func.lower(User.email) == email)).scalars().first()
    return found


def _parent_row(db: Session, cid: str, r: dict, file_parents: Dict[str, str]):
    """The row's parent as a dict, None when the row has no parent, or an error message."""
    raw_phone, pemail, pname = r.get("parent_phone", ""), r.get("parent_email", "").lower(), r.get("parent_name", "")
    if not (raw_phone or pemail or pname):
        return None
    if not raw_phone:
        return "parent_phone is required when a parent is given (parents sign in with their mobile number)"
    pphone = _norm_phone(raw_phone)
    if pphone is None:
        return "parent_phone must be a 10-digit mobile number"
    if pemail and not EMAIL_RE.match(pemail):
        return "parent_email is invalid"
    if r.get("parent_consent", "").lower() not in CONSENT_YES:
        return "parent details need parent_consent=yes: record the parent's consent before their data is saved"
    ref = r.get("parent_consent_ref", "")
    if len(ref) < 2 or len(ref) > 200:
        return "parent_consent_ref is required: the consent form number or scanned file name"
    if pemail:
        owner = db.execute(select(User).where(func.lower(User.email) == pemail)).scalars().first()
        if owner is not None and (owner.role != "parent" or owner.college_id != cid or (owner.phone and owner.phone != pphone)):
            return "parent_email already belongs to another account"
    if pphone in file_parents and pemail and file_parents[pphone] and file_parents[pphone] != pemail:
        return "the same parent_phone has two different parent_email values in this file"
    file_parents[pphone] = file_parents.get(pphone) or pemail
    return {"phone": pphone, "email": pemail or None, "name": pname, "consent_ref": ref}


@router.post("/students/import")
async def import_students(file: UploadFile = File(...), dry_run: bool = Query(True),
                          current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    cid = current_user.college_id
    raw = await file.read()
    check_upload(current_user, raw, file.filename, college_id=cid, purpose="student_import")     # even though it is not stored
    rows = _parse_csv(raw)
    branches = {b.code.upper(): b for b in db.execute(select(Branch).where(Branch.college_id == cid)).scalars()}
    batches = {(x.branch_id, x.short_name.upper()): x for x in db.execute(select(Batch).where(Batch.college_id == cid)).scalars()}
    existing = {s.register_no: s for s in db.execute(select(Student).where(Student.college_id == cid)).scalars()}
    errors: List[dict] = []
    seen_reg, seen_email = set(), set()
    file_parents: Dict[str, str] = {}                           # parent phone -> email seen earlier in this file
    plan = []
    for i, r in enumerate(rows, start=2):                      # row 1 is the header
        def err(msg):
            errors.append({"row": i, "register_no": r.get("register_no", ""), "error": msg})
        reg, name, email = r.get("register_no", ""), r.get("name", ""), r.get("email", "").lower()
        if not reg or not re.fullmatch(r"[A-Za-z0-9\-]{3,32}", reg):
            err("register_no is missing or invalid"); continue
        if reg in seen_reg:
            err("register_no appears twice in this file"); continue
        seen_reg.add(reg)
        if len(name) < 2:
            err("name is missing"); continue
        if not EMAIL_RE.match(email):
            err("email is missing or invalid"); continue
        if email in seen_email:
            err("email appears twice in this file"); continue
        seen_email.add(email)
        br = branches.get(r.get("branch_code", "").upper())
        if br is None:
            err(f"branch_code {r.get('branch_code', '')!r} does not exist (add the branch first)"); continue
        bt = batches.get((br.id, r.get("batch", "").upper()))
        if bt is None:
            err(f"batch {r.get('batch', '')!r} does not exist in branch {br.code}"); continue
        if r.get("semester", "") != str(bt.semester):
            err(f"semester {r.get('semester', '')!r} does not match batch {bt.short_name} (semester {bt.semester})"); continue
        cur = existing.get(reg)
        owner = db.execute(select(User.id).where(func.lower(User.email) == email)).scalar_one_or_none()
        if owner and (cur is None or owner != cur.user_id):
            err("email already belongs to another account"); continue
        phone = _norm_phone(r.get("phone", "")) if r.get("phone") else None
        if r.get("phone") and phone is None:
            err("phone must be a 10-digit mobile number"); continue
        parent = _parent_row(db, cid, r, file_parents)
        if isinstance(parent, str):
            err(parent); continue
        plan.append((r, br, bt, cur, email, phone, parent))

    summary = {"rows": len(rows), "errors": len(errors), "new": sum(1 for p in plan if p[3] is None),
               "updated": sum(1 for p in plan if p[3] is not None), "parents_linked": sum(1 for p in plan if p[6]),
               "parents_without_email": sum(1 for p in plan if p[6] and not p[6]["email"])}
    if dry_run or errors:
        return {"dry_run": True, "can_import": not errors and bool(plan), "summary": summary, "errors": errors[:50]}

    new_users = []
    consents = parents_new = 0
    for r, br, bt, cur, email, phone, p in plan:
        name = r["name"]
        if cur is None:
            uid = f"usr_{uuid.uuid4().hex[:16]}"
            db.add(User(id=uid, college_id=cid, email=email, name=name, phone=phone, role="student", avatar_initials=_initials(name),
                        language_pref="en", hashed_password=get_password_hash(secrets.token_urlsafe(32))))   # no usable password
            db.flush()
            cur = Student(id=f"std_{uuid.uuid4().hex[:16]}", college_id=cid, user_id=uid, register_no=r["register_no"])
            db.add(cur)
            new_users.append(uid)
        else:
            u = db.get(User, cur.user_id)
            u.name, u.email, u.phone = name, email, phone or u.phone
        cur.branch, cur.branch_id, cur.batch_id = br.name, br.id, bt.id
        cur.semester, cur.batch_name, cur.track, cur.academic_year = bt.semester, bt.name, bt.track, bt.academic_year
        db.flush()
        if p:
            # One parent account per mobile number in this college, linked to each of their children.
            parent = _find_parent(db, cid, p["phone"], p["email"])
            if parent is None:
                pname = p["name"] or f"Parent of {name}"
                parent = User(id=f"usr_{uuid.uuid4().hex[:16]}", college_id=cid, email=p["email"] or f"{p['phone']}@parents.invalid",
                              name=pname, phone=p["phone"], role="parent", avatar_initials=_initials(pname), language_pref="ta",
                              hashed_password=get_password_hash(secrets.token_urlsafe(32)))       # parents sign in with OTP
                db.add(parent)
                parents_new += 1
            else:
                if p["email"] and parent.email.endswith("@parents.invalid"):
                    parent.email = p["email"]
                if p["name"] and parent.name.startswith("Parent of "):
                    parent.name = p["name"]
            db.flush()
            # DPDP: the consent (paper form checked by the college) is recorded with the parent data in the
            # same transaction; a row without it never gets here (_parent_row rejects it).
            if consent_svc.current(db, cur.id, "parent_data_processing") != "granted":
                consent_svc.record(db, college_id=cid, student_id=cur.id, granted_by=parent.id, purpose="parent_data_processing",
                                   status="granted", method="paper_form_upload",
                                   evidence_ref=f"import:{p['consent_ref']}; recorded_by:{current_user.sub}"[:512])
                consents += 1
            linked = db.execute(select(ParentStudent.id).where(ParentStudent.parent_user_id == parent.id,
                                                               ParentStudent.student_id == cur.id)).first()
            if not linked:
                db.add(ParentStudent(id=f"ps_{uuid.uuid4().hex[:16]}", college_id=cid, parent_user_id=parent.id,
                                     student_id=cur.id, relationship="Parent"))
    if keycloak_mode():
        for uid in new_users:
            emit(db, "identity.invite_user", {"user_id": uid}, college_id=cid, entity_type="user", entity_id=uid)
    summary.update({"parents_new": parents_new, "consents_recorded": consents})
    record_audit(db, current_user, "students.imported", "college", cid, summary)        # counts only
    db.commit()
    return {"dry_run": False, "imported": True, "summary": summary, "errors": []}
