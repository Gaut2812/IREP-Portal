"""Screens 21 (trainer reports) and 16 (parent progress reports): link L22.
Release rule (INTERCONNECT §5.1.1): a parent's monthly card is released only after
the trainer approves it. Spec: docs/screens/21-16-20-49-reports-and-support.md"""
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_child_for_parent, get_trainer_batch_ids, get_trainer_for_user, get_user_name
from models.schema import MonthlyCard, ParentStudent, SkillScore, Student, User
from services.audit import record_audit
from services.consent import is_granted
from services.notifications import notify_user
from services.parent_overview import month_label
from services.reports import render_pdf
from services.storage import get_storage
from services.translation import translate

router = APIRouter(tags=["Monthly cards"])
TRAINER = require_role(["trainer"])
PARENT = require_role(["parent"])
RELEASED = ("approved", "sent")


class CardEdit(BaseModel):
    trainer_remark_en: Optional[str] = Field(default=None, max_length=2000)
    trainer_remark_ta: Optional[str] = Field(default=None, max_length=2000)
    how_to_help_en: Optional[str] = Field(default=None, max_length=2000)
    how_to_help_ta: Optional[str] = Field(default=None, max_length=2000)


class MonthIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")


class BulkApprove(BaseModel):
    card_ids: List[str] = Field(min_length=1, max_length=200)


def _parse_month(month: Optional[str]) -> tuple:
    if not month:
        today = datetime.date.today()
        return today.year, today.month
    try:
        y, m = (int(x) for x in month.split("-"))
        datetime.date(y, m, 1)
        return y, m
    except ValueError:
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")


def _prev(y: int, m: int) -> tuple:
    return (y - 1, 12) if m == 1 else (y, m - 1)


def _card_out(c: MonthlyCard, lang: str, name: Optional[str] = None) -> dict:
    ta = lang == "ta"

    def pick(row, key):
        return row.get(f"{key}_ta") if ta and row.get(f"{key}_ta") else row.get(key if key in ("prev", "curr") else f"{key}_en")
    return {
        "id": c.id, "student_id": c.student_id, "name": name, "year": c.year, "month": c.month,
        "month_label": f"{month_label(c.month, lang)} {c.year}", "status": c.status,
        "rows": [{"area": pick(r, "area"), "prev": pick(r, "prev"), "curr": pick(r, "curr"), "status": pick(r, "status"),
                  "color": r.get("color", "green")} for r in (c.rows or [])],
        "trainer_remark": c.trainer_remark_ta if ta and c.trainer_remark_ta else c.trainer_remark_en,
        "how_to_help": c.how_to_help_ta if ta and c.how_to_help_ta else c.how_to_help_en,
        "trainer_remark_en": c.trainer_remark_en, "trainer_remark_ta": c.trainer_remark_ta,
        "how_to_help_en": c.how_to_help_en, "how_to_help_ta": c.how_to_help_ta,
        "trainer_name": c.trainer_name, "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        # the trainer writes English only; Tamil is filled in by the translation service (fill_tamil)
        "missing": [k for k in ("trainer_remark_en", "how_to_help_en") if not (getattr(c, k) or "").strip()],
    }


# ------------------------------------------------------------------ Screen 21

def _my_students(db: Session, user: TokenPayload) -> List[Student]:
    batch_ids = get_trainer_batch_ids(get_trainer_for_user(user, db), db) or ["_"]
    return db.execute(select(Student).where(Student.college_id == user.college_id, Student.batch_id.in_(batch_ids))).scalars().all()


def _trainer_card(db: Session, card_id: str, user: TokenPayload) -> MonthlyCard:
    card = db.execute(select(MonthlyCard).where(MonthlyCard.id == card_id, MonthlyCard.college_id == user.college_id)).scalar_one_or_none()
    if not card or card.student_id not in {s.id for s in _my_students(db, user)}:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@router.get("/trainer/reports")
def trainer_cards(month: Optional[str] = None, lang: str = "en", current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    y, m = _parse_month(month)
    students = _my_students(db, current_user)
    names = dict(db.execute(select(User.id, User.name).where(User.id.in_([s.user_id for s in students] or ["_"]))).all())
    cards = {c.student_id: c for c in db.execute(select(MonthlyCard).where(
        MonthlyCard.student_id.in_([s.id for s in students] or ["_"]), MonthlyCard.year == y, MonthlyCard.month == m)).scalars()}
    rows = []
    for s in sorted(students, key=lambda s: (s.batch_name or "", names.get(s.user_id) or "")):
        c = cards.get(s.id)
        rows.append({"student_id": s.id, "name": names.get(s.user_id, "Student"), "batch": s.batch_name,
                     "card_id": c.id if c else None, "status": c.status if c else "none",
                     "ready": bool(c) and c.status == "draft" and not _card_out(c, "en")["missing"]})
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("none", "draft", "approved", "sent")}
    return {"month": f"{y:04d}-{m:02d}", "month_label": f"{month_label(m, lang)} {y}", "students": rows, "counts": counts}


def _rows_from_data(db: Session, st: Student, prev: Optional[MonthlyCard]) -> list:
    before = {r.get("area_en"): r.get("curr") for r in (prev.rows if prev else [])}
    comm = db.execute(select(SkillScore.percentage).where(SkillScore.student_id == st.id, SkillScore.skill_key == "communication")).scalar_one_or_none()
    comm5 = f"{max(1, min(5, round((comm or 0) / 20)))}/5"

    def row(area_en, area_ta, curr, good):
        return {"area_en": area_en, "area_ta": area_ta, "prev": before.get(area_en, "-"), "curr": curr,
                "status_en": "On track" if good else "Needs practice", "status_ta": "சரியான பாதையில்" if good else "பயிற்சி தேவை",
                "color": "green" if good else "amber"}
    return [
        row("Coding (problems solved)", "கோடிங் (தீர்க்கப்பட்டவை)", str(st.problems_solved),
            st.problems_solved > int(before.get("Coding (problems solved)", "0") or 0) if str(before.get("Coding (problems solved)", "0")).isdigit() else True),
        row("Readiness score", "தயார்நிலை மதிப்பெண்", str(st.readiness_score), st.readiness_score >= 60),
        row("Attendance", "வருகை", f"{st.attendance_pct}%", st.attendance_pct >= 85),
        row("Communication", "தொடர்புத் திறன்", comm5, (comm or 0) >= 70),
    ]


@router.post("/trainer/reports/generate")
def generate_drafts(req: MonthIn, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    y, m = _parse_month(req.month)
    py, pm = _prev(y, m)
    trainer_name = get_user_name(db, current_user.sub, "Trainer")
    made = 0
    for st in _my_students(db, current_user):
        if db.execute(select(MonthlyCard.id).where(MonthlyCard.student_id == st.id, MonthlyCard.year == y, MonthlyCard.month == m)).first():
            continue
        prev = db.execute(select(MonthlyCard).where(MonthlyCard.student_id == st.id, MonthlyCard.year == py, MonthlyCard.month == pm)).scalar_one_or_none()
        db.add(MonthlyCard(id=f"mc_{st.id}_{y:04d}{m:02d}"[:64], college_id=st.college_id, student_id=st.id, year=y, month=m,
                           rows=_rows_from_data(db, st, prev), trainer_name=trainer_name, status="draft"))
        made += 1
    db.commit()
    return {"success": True, "created": made}


@router.get("/trainer/reports/{card_id}")
def trainer_card(card_id: str, lang: str = "en", current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    c = _trainer_card(db, card_id, current_user)
    st = db.get(Student, c.student_id)
    return _card_out(c, lang, get_user_name(db, st.user_id, "Student"))


@router.put("/trainer/reports/{card_id}")
def edit_card(card_id: str, req: CardEdit, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    c = _trainer_card(db, card_id, current_user)
    if c.status != "draft":
        raise HTTPException(status_code=409, detail="This card is already released and cannot be edited")
    sent = req.model_dump(exclude_unset=True)
    for k, v in sent.items():
        setattr(c, k, (v or "").strip() or None)
    # an English edit refreshes its Tamil text unless the same request also sent Tamil explicitly
    fill_tamil(db, c, refresh=[base for base in TA_PAIRS if f"{base}_en" in sent and f"{base}_ta" not in sent])
    db.commit()
    return _card_out(c, "en")


TA_PAIRS = ("trainer_remark", "how_to_help")


def fill_tamil(db: Session, c: MonthlyCard, refresh: Optional[List[str]] = None) -> None:
    """Parents read the card in Tamil (rule 9): translate each English field into its _ta field when that is
    empty, or when the English was just edited (refresh). Production uses TRANSLATE_ADAPTER=libretranslate."""
    for base in TA_PAIRS:
        en = getattr(c, f"{base}_en")
        if en and (not getattr(c, f"{base}_ta") or base in (refresh or [])):
            setattr(c, f"{base}_ta", translate(db, en, "ta", c.college_id, src="en"))
        elif not en and base in (refresh or []):
            setattr(c, f"{base}_ta", None)


def card_pdf(c: MonthlyCard, child_name: str) -> str:
    """Render the released card (English PDF; Tamil glyphs need WeasyPrint, see services/reports.py)."""
    key = f"cards/{c.id}.pdf"
    lines = [f"Student: {child_name}", f"Month: {month_label(c.month, 'en')} {c.year}", ""]
    lines += [f"{r.get('area_en')}: {r.get('prev')} -> {r.get('curr')} ({r.get('status_en')})" for r in (c.rows or [])]
    lines += ["", f"Trainer: {c.trainer_name or ''}", f"Remark: {c.trainer_remark_en or ''}"[:110], f"How to help: {c.how_to_help_en or ''}"[:110]]
    get_storage().put(key, render_pdf("IREP monthly progress card", lines), "application/pdf")
    return key


def _approve(db: Session, c: MonthlyCard, user: TokenPayload) -> Optional[str]:
    """Release one card. Returns a reason when it cannot be released."""
    if c.status != "draft":
        return "already released"
    missing = _card_out(c, "en")["missing"]
    if missing:
        return "add the remark and the help text"
    fill_tamil(db, c)
    st = db.get(Student, c.student_id)
    name = get_user_name(db, st.user_id, "Student")
    c.status, c.approved_by, c.approved_at = "approved", user.sub, datetime.datetime.utcnow()
    c.pdf_path = card_pdf(c, name)
    label_en, label_ta = f"{month_label(c.month, 'en')} {c.year}", f"{month_label(c.month, 'ta')} {c.year}"
    parents = db.execute(select(ParentStudent.parent_user_id).where(ParentStudent.student_id == st.id,
                                                                    ParentStudent.college_id == st.college_id)).scalars().all()
    for pid in parents:
        notify_user(db, pid, f"{name}'s {label_en} progress card is ready", c.trainer_remark_en,
                    title_ta=f"{name}-இன் {label_ta} முன்னேற்ற அட்டை தயார்", body_ta=c.trainer_remark_ta,
                    kind="report", link="/parent/reports", channels=("in_app", "sms"), college_id=c.college_id)
    record_audit(db, user, "monthly_card.released", "monthly_card", c.id, {"student_id": st.id, "parents": len(parents)})
    return None


@router.post("/trainer/reports/{card_id}/approve")
def approve_card(card_id: str, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    c = _trainer_card(db, card_id, current_user)
    why = _approve(db, c, current_user)
    if why:
        raise HTTPException(status_code=409 if why == "already released" else 422, detail=f"Cannot release: {why}")
    db.commit()
    return _card_out(c, "en")


@router.post("/trainer/reports/approve")
def approve_many(req: BulkApprove, current_user: TokenPayload = Depends(TRAINER), db: Session = Depends(get_db)):
    released, skipped = [], []
    for cid in req.card_ids:
        try:
            c = _trainer_card(db, cid, current_user)
        except HTTPException:
            skipped.append({"card_id": cid, "reason": "not found"})
            continue
        why = _approve(db, c, current_user)
        (skipped.append({"card_id": cid, "reason": why}) if why else released.append(cid))
    db.commit()
    return {"released": released, "skipped": skipped}


# ------------------------------------------------------------------ Screen 16

def _child_ok(db: Session, user: TokenPayload, child_id: Optional[str]) -> Student:
    child = get_child_for_parent(user, db, child_id)
    if not is_granted(db, child.id, "parent_data_processing"):
        raise HTTPException(status_code=403, detail="Parent-data consent is needed first (see the overview)")
    return child


def _parent_card(db: Session, user: TokenPayload, card_id: str) -> tuple:
    c = db.execute(select(MonthlyCard).where(MonthlyCard.id == card_id, MonthlyCard.college_id == user.college_id,
                                             MonthlyCard.status.in_(RELEASED))).scalar_one_or_none()
    if not c or not db.execute(select(ParentStudent.id).where(ParentStudent.parent_user_id == user.sub,
                                                               ParentStudent.student_id == c.student_id)).first():
        raise HTTPException(status_code=404, detail="Report not found")
    child = _child_ok(db, user, c.student_id)
    return c, child


@router.get("/parent/reports")
def parent_cards(child_id: Optional[str] = None, lang: str = "en", current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    child = get_child_for_parent(current_user, db, child_id)
    name = get_user_name(db, child.user_id, "Student")
    if not is_granted(db, child.id, "parent_data_processing"):
        return {"consent_required": True, "ward": {"id": child.id, "name": name}, "cards": []}
    cards = db.execute(select(MonthlyCard).where(MonthlyCard.student_id == child.id, MonthlyCard.college_id == child.college_id,
                                                 MonthlyCard.status.in_(RELEASED))
                       .order_by(MonthlyCard.year.desc(), MonthlyCard.month.desc())).scalars().all()
    return {"consent_required": False, "ward": {"id": child.id, "name": name},
            "cards": [{**_card_out(c, lang, name), "pdf_url": f"/api/v1/parent/reports/{c.id}/pdf"} for c in cards]}


@router.get("/parent/reports/{card_id}")
def parent_card(card_id: str, lang: str = "en", current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    c, child = _parent_card(db, current_user, card_id)
    return {**_card_out(c, lang, get_user_name(db, child.user_id, "Student")), "pdf_url": f"/api/v1/parent/reports/{c.id}/pdf"}


@router.get("/parent/reports/{card_id}/pdf")
def parent_card_pdf(card_id: str, current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    c, child = _parent_card(db, current_user, card_id)
    storage = get_storage()
    if not c.pdf_path or not storage.exists(c.pdf_path):
        c.pdf_path = card_pdf(c, get_user_name(db, child.user_id, "Student"))       # seeded cards: render on first download
    db.commit()
    return Response(content=storage.get(c.pdf_path), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="progress-{c.year}-{c.month:02d}.pdf"'})
