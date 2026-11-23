"""Screens 02 (college settings: surveys) and 40 (parent feedback survey): link L26, survey sent,
responses returned. Results are aggregates; comments are shown without names.
Spec: docs/screens/41-40-messages-surveys.md"""
import datetime
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_parent_children
from models.schema import ParentStudent, Survey, SurveyResponse
from services.audit import record_audit
from services.notifications import notify_user

router = APIRouter(tags=["Surveys"])
COLLEGE, PARENT = require_role(["college_admin"]), require_role(["parent"])
KINDS = ("rating", "choice", "text")
MIN_RESPONSES_FOR_RESULTS = 3          # below this, results could identify a parent


class QuestionIn(BaseModel):
    kind: str
    text_en: str = Field(min_length=3, max_length=500)
    text_ta: Optional[str] = Field(default=None, max_length=500)
    options_en: Optional[List[str]] = None
    options_ta: Optional[List[str]] = None
    required: bool = True


class SurveyIn(BaseModel):
    title_en: str = Field(min_length=3, max_length=255)
    title_ta: Optional[str] = Field(default=None, max_length=255)
    closes_on: Optional[datetime.date] = None
    questions: List[QuestionIn] = Field(min_length=1, max_length=20)


class AnswersIn(BaseModel):
    answers: Dict[str, Any]


def _validate(req: SurveyIn) -> list:
    out = []
    for i, q in enumerate(req.questions, start=1):
        if q.kind not in KINDS:
            raise HTTPException(status_code=422, detail="Question kind must be rating, choice or text")
        if q.kind == "choice" and (not q.options_en or len(q.options_en) < 2):
            raise HTTPException(status_code=422, detail="A choice question needs at least two options")
        if q.kind == "choice" and q.options_ta and len(q.options_ta) != len(q.options_en):
            raise HTTPException(status_code=422, detail="Give a Tamil text for every option")
        out.append({"id": f"q{i}", **q.model_dump()})
    return out


def _out(s: Survey, lang: str = "en") -> dict:
    ta = lang == "ta"
    return {"id": s.id, "title": s.title_ta if ta and s.title_ta else s.title_en, "title_en": s.title_en, "title_ta": s.title_ta,
            "status": s.status, "closes_on": s.closes_on.isoformat() if s.closes_on else None,
            "published_at": s.published_at.isoformat() if s.published_at else None,
            "questions": [{"id": q["id"], "kind": q["kind"], "required": q.get("required", True),
                           "text": q.get("text_ta") if ta and q.get("text_ta") else q["text_en"],
                           "options": (q.get("options_ta") if ta and q.get("options_ta") else q.get("options_en")) or []}
                          for q in s.questions]}


def _college_survey(db: Session, survey_id: str, user: TokenPayload) -> Survey:
    s = db.execute(select(Survey).where(Survey.id == survey_id, Survey.college_id == user.college_id)).scalar_one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="Survey not found")
    return s


# ------------------------------------------------------------------ Screen 02 (college)

@router.get("/college/surveys")
def list_surveys(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    rows = db.execute(select(Survey).where(Survey.college_id == current_user.college_id).order_by(Survey.created_at.desc())).scalars().all()
    counts = dict(db.execute(select(SurveyResponse.survey_id, func.count(SurveyResponse.id))
                             .where(SurveyResponse.survey_id.in_([s.id for s in rows] or ["_"])).group_by(SurveyResponse.survey_id)).all())
    return {"surveys": [{**_out(s), "responses": counts.get(s.id, 0)} for s in rows]}


@router.post("/college/surveys", status_code=status.HTTP_201_CREATED)
def create_survey(req: SurveyIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    s = Survey(id=f"sv_{uuid.uuid4().hex[:16]}", college_id=current_user.college_id, title_en=req.title_en.strip(),
               title_ta=(req.title_ta or "").strip() or None, closes_on=req.closes_on, questions=_validate(req),
               status="draft", created_by=current_user.sub)
    db.add(s)
    db.commit()
    return _out(s)


@router.put("/college/surveys/{survey_id}")
def edit_survey(survey_id: str, req: SurveyIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    s = _college_survey(db, survey_id, current_user)
    if s.status != "draft":
        raise HTTPException(status_code=409, detail="Only drafts can be edited")
    s.title_en, s.title_ta, s.closes_on, s.questions = req.title_en.strip(), (req.title_ta or "").strip() or None, req.closes_on, _validate(req)
    db.commit()
    return _out(s)


@router.post("/college/surveys/{survey_id}/publish")
def publish_survey(survey_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    """L26: survey sent. Every linked parent in the college is notified (in-app and SMS)."""
    s = _college_survey(db, survey_id, current_user)
    if s.status != "draft":
        raise HTTPException(status_code=409, detail="This survey is already published or closed")
    if not s.title_ta or any(not q.get("text_ta") for q in s.questions):
        raise HTTPException(status_code=422, detail="Add the Tamil text for the title and every question before publishing")
    if s.closes_on and s.closes_on < datetime.date.today():
        raise HTTPException(status_code=422, detail="The closing date has passed")
    s.status, s.published_at = "published", datetime.datetime.utcnow()
    parents = sorted(set(db.execute(select(ParentStudent.parent_user_id).where(ParentStudent.college_id == s.college_id)).scalars()))
    for pid in parents:
        notify_user(db, pid, f"Please share your feedback: {s.title_en}", "It takes about two minutes.",
                    title_ta=f"உங்கள் கருத்தைப் பகிரவும்: {s.title_ta}", body_ta="சுமார் இரண்டு நிமிடங்கள் ஆகும்.",
                    kind="survey", link=f"/parent/surveys?survey={s.id}", channels=("in_app", "sms"), college_id=s.college_id)
    record_audit(db, current_user, "survey.published", "survey", s.id, {"parents": len(parents), "questions": len(s.questions)})
    db.commit()
    return {**_out(s), "notified": len(parents)}


@router.post("/college/surveys/{survey_id}/close")
def close_survey(survey_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    s = _college_survey(db, survey_id, current_user)
    s.status = "closed"
    record_audit(db, current_user, "survey.closed", "survey", s.id, None)
    db.commit()
    return _out(s)


@router.get("/college/surveys/{survey_id}/results")
def survey_results(survey_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    """L26: responses returned, as aggregates. Comments come back without names, and nothing is
    shown until enough parents answered that no one can be picked out."""
    s = _college_survey(db, survey_id, current_user)
    answers = [r.answers for r in db.execute(select(SurveyResponse).where(SurveyResponse.survey_id == s.id)).scalars()]
    invited = db.execute(select(func.count(func.distinct(ParentStudent.parent_user_id))).where(ParentStudent.college_id == s.college_id)).scalar_one()
    base = {"survey": _out(s), "responses": len(answers), "invited": invited}
    if len(answers) < MIN_RESPONSES_FOR_RESULTS:
        return {**base, "hidden": True, "min_responses": MIN_RESPONSES_FOR_RESULTS, "questions": []}
    out = []
    for q in s.questions:
        vals = [a.get(q["id"]) for a in answers if a.get(q["id"]) not in (None, "")]
        row = {"id": q["id"], "kind": q["kind"], "text": q["text_en"], "answered": len(vals)}
        if q["kind"] == "rating":
            nums = [int(v) for v in vals]
            row.update({"average": round(sum(nums) / len(nums), 2) if nums else None, "distribution": {str(k): nums.count(k) for k in range(1, 6)}})
        elif q["kind"] == "choice":
            row["counts"] = {opt: sum(1 for v in vals if v == opt) for opt in q["options_en"]}
        else:
            row["comments"] = sorted(str(v)[:1000] for v in vals)        # sorted: no link back to who wrote what
        out.append(row)
    return {**base, "hidden": False, "questions": out}


# ------------------------------------------------------------------ Screen 40 (parent)

@router.get("/parent/surveys")
def parent_surveys(lang: str = "en", current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    if not get_parent_children(current_user, db):
        raise HTTPException(status_code=404, detail="No linked child")
    rows = db.execute(select(Survey).where(Survey.college_id == current_user.college_id, Survey.status == "published")
                      .order_by(Survey.published_at.desc())).scalars().all()
    done = set(db.execute(select(SurveyResponse.survey_id).where(SurveyResponse.parent_user_id == current_user.sub)).scalars())
    today = datetime.date.today()
    return {"surveys": [{**_out(s, lang), "answered": s.id in done, "open": not s.closes_on or s.closes_on >= today} for s in rows]}


@router.post("/parent/surveys/{survey_id}/responses", status_code=status.HTTP_201_CREATED)
def respond(survey_id: str, req: AnswersIn, current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    s = db.execute(select(Survey).where(Survey.id == survey_id, Survey.college_id == current_user.college_id,
                                        Survey.status == "published")).scalar_one_or_none()
    if s is None or not get_parent_children(current_user, db):
        raise HTTPException(status_code=404, detail="Survey not found")
    if s.closes_on and s.closes_on < datetime.date.today():
        raise HTTPException(status_code=409, detail="This survey has closed")
    if db.execute(select(SurveyResponse.id).where(SurveyResponse.survey_id == s.id, SurveyResponse.parent_user_id == current_user.sub)).first():
        raise HTTPException(status_code=409, detail="You have already answered this survey. Thank you!")
    clean = {}
    for q in s.questions:
        v = req.answers.get(q["id"])
        if v in (None, ""):
            if q.get("required", True):
                raise HTTPException(status_code=422, detail=f"Please answer: {q['text_en']}")
            continue
        if q["kind"] == "rating" and (not isinstance(v, int) or not 1 <= v <= 5):
            raise HTTPException(status_code=422, detail="Ratings are 1 to 5")
        if q["kind"] == "choice":
            opts_ta = q.get("options_ta") or []
            if v in opts_ta:                                   # answered in Tamil: store the English option
                v = q["options_en"][opts_ta.index(v)]
            if v not in q["options_en"]:
                raise HTTPException(status_code=422, detail="Pick one of the options")
        if q["kind"] == "text":
            v = str(v).strip()[:1000]
        clean[q["id"]] = v
    db.add(SurveyResponse(id=f"svr_{uuid.uuid4().hex[:16]}", college_id=s.college_id, survey_id=s.id,
                          parent_user_id=current_user.sub, answers=clean))
    db.commit()
    return {"survey_id": s.id, "answered": True}
