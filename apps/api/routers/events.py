"""Screens 42 (college events) and 17 (parent events): links L05 and L29.
Spec: docs/screens/42-17-14-events-and-at-risk.md"""
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import TokenPayload, require_role
from core.tenant import get_child_for_parent, get_user_name
from models.schema import Batch, DiscussionGroup, Event, GroupMessage, ParentStudent, Rsvp, Student
from services.audit import record_audit
from services.drives import ensure_for_event as ensure_drive_for_event
from services.notifications import notify_user

router = APIRouter(tags=["Events"])
COLLEGE = require_role(["college_admin", "placement_officer"])
PARENT = require_role(["parent"])

KINDS = ("event", "guest", "demo_day", "meeting", "drive", "placement_update")
AUDIENCES = ("students", "parents", "all")
PLACEMENT_KINDS = ("drive", "placement_update")
KIND_TA = {"event": "நிகழ்வு", "guest": "விருந்தினர் உரை", "demo_day": "டெமோ நாள்", "meeting": "கூட்டம்",
           "drive": "மாதிரி வேலைவாய்ப்பு முகாம்", "placement_update": "வேலைவாய்ப்பு அறிவிப்பு"}


class EventIn(BaseModel):
    title_en: str = Field(min_length=3, max_length=255)
    title_ta: Optional[str] = Field(default=None, max_length=255)
    kind: str = "event"
    starts_at: datetime.datetime
    ends_at: Optional[datetime.datetime] = None
    location: Optional[str] = Field(default=None, max_length=255)
    description_en: Optional[str] = Field(default=None, max_length=4000)
    description_ta: Optional[str] = Field(default=None, max_length=4000)
    audience: str = "all"
    batch_id: Optional[str] = None
    rsvp_enabled: bool = True


class RsvpIn(BaseModel):
    status: str = "yes"
    guests: int = 1
    child_id: Optional[str] = None


def _when(e: Event) -> str:
    return e.starts_at.strftime("%a, %b %d · %I:%M %p").replace(" 0", " ")


def _counts(db: Session, event_ids: list) -> dict:
    """L05 counts up: yes/maybe/no and expected guests per event (aggregates only, no names)."""
    out = {eid: {"yes": 0, "maybe": 0, "no": 0, "guests": 0} for eid in event_ids}
    for eid, st, n, guests in db.execute(
            select(Rsvp.event_id, Rsvp.status, func.count(Rsvp.id), func.coalesce(func.sum(Rsvp.guests), 0))
            .where(Rsvp.event_id.in_(event_ids or ["_"])).group_by(Rsvp.event_id, Rsvp.status)).all():
        if st in out[eid]:
            out[eid][st] = n
        if st == "yes":
            out[eid]["guests"] = int(guests)
    return out


def _college_row(e: Event, counts: dict) -> dict:
    return {"id": e.id, "title_en": e.title_en, "title_ta": e.title_ta, "kind": e.kind, "starts_at": e.starts_at.isoformat(),
            "ends_at": e.ends_at.isoformat() if e.ends_at else None, "when": _when(e), "location": e.location,
            "description_en": e.description_en, "description_ta": e.description_ta, "audience": e.audience, "batch_id": e.batch_id,
            "rsvp_enabled": e.rsvp_enabled, "status": e.status, "published_at": e.published_at.isoformat() if e.published_at else None,
            "rsvp": counts.get(e.id, {"yes": 0, "maybe": 0, "no": 0, "guests": 0})}


def _college_event(db: Session, event_id: str, user: TokenPayload) -> Event:
    e = db.execute(select(Event).where(Event.id == event_id, Event.college_id == user.college_id,
                                       Event.student_id.is_(None))).scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Event not found")
    return e


def _validate(db: Session, req: EventIn, user: TokenPayload) -> None:
    if req.kind not in KINDS:
        raise HTTPException(status_code=422, detail="Unknown event kind")
    if req.audience not in AUDIENCES:
        raise HTTPException(status_code=422, detail="Audience must be students, parents or all")
    if req.ends_at and req.ends_at <= req.starts_at:
        raise HTTPException(status_code=422, detail="The event must end after it starts")
    if req.batch_id and not db.execute(select(Batch.id).where(Batch.id == req.batch_id, Batch.college_id == user.college_id)).first():
        raise HTTPException(status_code=404, detail="Batch not found")


# ---------------------------------------------------------------- Screen 42

@router.get("/college/events")
def list_college_events(current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=60)
    events = db.execute(select(Event).where(Event.college_id == current_user.college_id, Event.student_id.is_(None),
                                            Event.starts_at >= since).order_by(Event.starts_at)).scalars().all()
    counts = _counts(db, [e.id for e in events])
    batches = db.execute(select(Batch.id, Batch.name).where(Batch.college_id == current_user.college_id).order_by(Batch.name)).all()
    return {"events": [_college_row(e, counts) for e in events], "kinds": list(KINDS),
            "batches": [{"id": b, "name": n} for b, n in batches]}


@router.post("/college/events", status_code=status.HTTP_201_CREATED)
def create_event(req: EventIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    _validate(db, req, current_user)
    e = Event(id=f"evt_{uuid.uuid4().hex[:16]}", college_id=current_user.college_id, status="draft", created_by=current_user.sub,
              **req.model_dump())
    db.add(e)
    db.flush()
    record_audit(db, current_user, "event.created", "event", e.id, {"kind": e.kind, "audience": e.audience})
    drive = ensure_drive_for_event(db, e, current_user.sub)          # L29: a mock drive is an event type (-> 38)
    if drive is not None:
        record_audit(db, current_user, "drive.created", "mock_drive", drive.id, {"event_id": e.id})
    db.commit()
    return _college_row(e, {})


@router.get("/college/events/{event_id}")
def get_event(event_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    e = _college_event(db, event_id, current_user)
    return _college_row(e, _counts(db, [e.id]))


@router.put("/college/events/{event_id}")
def update_event(event_id: str, req: EventIn, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    e = _college_event(db, event_id, current_user)
    if e.status != "draft":
        raise HTTPException(status_code=409, detail="Only drafts can be edited; cancel the event and create a new one")
    _validate(db, req, current_user)
    for k, v in req.model_dump().items():
        setattr(e, k, v)
    ensure_drive_for_event(db, e, current_user.sub)                  # L29: kind changed to drive, or a new batch
    db.commit()
    return _college_row(e, {})


def _audience_users(db: Session, e: Event):
    q = select(Student).where(Student.college_id == e.college_id)
    if e.batch_id:
        q = q.where(Student.batch_id == e.batch_id)
    students = db.execute(q).scalars().all()
    student_users = [s.user_id for s in students if s.user_id] if e.audience in ("students", "all") else []
    parent_users = sorted(set(db.execute(select(ParentStudent.parent_user_id).where(
        ParentStudent.college_id == e.college_id, ParentStudent.student_id.in_([s.id for s in students] or ["_"]))).scalars())) \
        if e.audience in ("parents", "all") else []
    return student_users, parent_users


@router.post("/college/events/{event_id}/publish")
def publish_event(event_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    e = _college_event(db, event_id, current_user)
    if e.status != "draft":
        raise HTTPException(status_code=409, detail="This event is already published or cancelled")
    if not (e.title_ta or "").strip():
        raise HTTPException(status_code=422, detail="Add the Tamil title before publishing")
    if e.starts_at <= datetime.datetime.now():
        raise HTTPException(status_code=422, detail="The event must start in the future")
    e.status, e.published_at = "published", datetime.datetime.utcnow()
    ensure_drive_for_event(db, e, current_user.sub)
    students, parents = _audience_users(db, e)
    when = _when(e)
    for uid in students:
        notify_user(db, uid, f"New event: {e.title_en}", f"{when}" + (f" · {e.location}" if e.location else ""),
                    title_ta=f"புதிய நிகழ்வு: {e.title_ta}", body_ta=when, kind="event", link="/student", college_id=e.college_id)
    for uid in parents:
        notify_user(db, uid, f"Invitation: {e.title_en}", f"{when}. Open Events to reply." if e.rsvp_enabled else when,
                    title_ta=f"அழைப்பு: {e.title_ta}", body_ta=f"{when}. பதிலளிக்க நிகழ்வுகளைத் திறக்கவும்." if e.rsvp_enabled else when,
                    kind="event", link="/parent/events", channels=("in_app", "sms"), college_id=e.college_id)
    posted = 0
    if e.kind in PLACEMENT_KINDS:   # L29: placement-update post on 34
        me = get_user_name(db, current_user.sub, "Placement cell")
        groups = db.execute(select(DiscussionGroup).where(DiscussionGroup.college_id == e.college_id,
                                                          DiscussionGroup.kind == "announcements")).scalars().all()
        for g in groups:
            db.add(GroupMessage(id=f"gm_evt_{uuid.uuid4().hex[:14]}", college_id=e.college_id, group_id=g.id, sender_name=me,
                                sender_role="Placement cell", sender_initials="PC", sender_user_id=current_user.sub,
                                message_text=f"{KIND_TA.get(e.kind, '')} / {e.title_en}: {when}" + (f", {e.location}" if e.location else "")
                                + (f". {e.description_en}" if e.description_en else ""),
                                timestamp_str=datetime.datetime.now().strftime("%I:%M %p").lstrip("0")))
            posted += 1
    record_audit(db, current_user, "event.published", "event", e.id,
                 {"students": len(students), "parents": len(parents), "placement_posts": posted})
    db.commit()
    return {**_college_row(e, _counts(db, [e.id])), "notified": {"students": len(students), "parents": len(parents)}, "placement_posts": posted}


@router.post("/college/events/{event_id}/cancel")
def cancel_event(event_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    e = _college_event(db, event_id, current_user)
    if e.status == "cancelled":
        raise HTTPException(status_code=409, detail="This event is already cancelled")
    was_published = e.status == "published"
    e.status = "cancelled"
    told = 0
    if was_published:
        for r in db.execute(select(Rsvp).where(Rsvp.event_id == e.id, Rsvp.status.in_(["yes", "maybe"]))).scalars():
            notify_user(db, r.parent_user_id, f"Cancelled: {e.title_en}", f"The event on {_when(e)} will not take place.",
                        title_ta=f"ரத்து: {e.title_ta or e.title_en}", body_ta=f"{_when(e)} அன்று நிகழ்வு நடைபெறாது.",
                        kind="event", link="/parent/events", channels=("in_app", "sms"), college_id=e.college_id)
            told += 1
    record_audit(db, current_user, "event.cancelled", "event", e.id, {"parents_told": told})
    db.commit()
    return {**_college_row(e, _counts(db, [e.id])), "parents_told": told}


# ---------------------------------------------------------------- Screen 17

def _parent_row(e: Event, r: Optional[Rsvp], lang: str, now: datetime.datetime) -> dict:
    ta = lang == "ta"
    return {"id": e.id, "title": e.title_ta if ta and e.title_ta else e.title_en, "kind": e.kind,
            "kind_label": KIND_TA.get(e.kind, e.kind) if ta else e.kind.replace("_", " ").capitalize(),
            "starts_at": e.starts_at.isoformat(), "when": _when(e), "location": e.location,
            "description": e.description_ta if ta and e.description_ta else e.description_en,
            "rsvp_enabled": e.rsvp_enabled, "upcoming": e.starts_at > now,
            "can_rsvp": e.rsvp_enabled and e.starts_at > now and e.status == "published",
            "rsvp_status": r.status if r else None, "guests": r.guests if r else 0}


def _parent_events_q(child: Student):
    return select(Event).where(Event.college_id == child.college_id, Event.status == "published", Event.student_id.is_(None),
                               Event.audience.in_(["parents", "all"]),
                               (Event.batch_id.is_(None)) | (Event.batch_id == child.batch_id))


@router.get("/parent/events")
def parent_events(lang: str = "en", child_id: Optional[str] = None, current_user: TokenPayload = Depends(PARENT),
                  db: Session = Depends(get_db)):
    child = get_child_for_parent(current_user, db, child_id)
    now = datetime.datetime.now()
    events = db.execute(_parent_events_q(child).where(Event.starts_at >= now - datetime.timedelta(days=30))
                        .order_by(Event.starts_at)).scalars().all()
    mine = {r.event_id: r for r in db.execute(select(Rsvp).where(Rsvp.parent_user_id == current_user.sub,
                                                                Rsvp.event_id.in_([e.id for e in events] or ["_"]))).scalars()}
    rows = [_parent_row(e, mine.get(e.id), lang, now) for e in events]
    return {"ward": {"id": child.id, "name": get_user_name(db, child.user_id, "Student")},
            "upcoming": [r for r in rows if r["upcoming"]], "past": [r for r in rows if not r["upcoming"]][::-1]}


@router.post("/parent/events/{event_id}/rsvp")
def rsvp_event(event_id: str, req: RsvpIn, current_user: TokenPayload = Depends(PARENT), db: Session = Depends(get_db)):
    """L05 RSVP up. Upcoming published events that take RSVPs, for the parent's child; else 404."""
    rsvp = save_parent_rsvp(db, current_user, event_id, req.status, req.guests, req.child_id)
    db.commit()
    return {"success": True, "event_id": event_id, "rsvp_status": rsvp.status, "guests": rsvp.guests}


def save_parent_rsvp(db: Session, current_user: TokenPayload, event_id: str, status_: str, guests: int,
                     child_id: Optional[str] = None) -> Rsvp:
    """One RSVP per parent per event (also used by the portfolio's Demo Day card). Caller commits."""
    if status_ not in ("yes", "no", "maybe"):
        raise HTTPException(status_code=422, detail="status must be yes, no or maybe")
    if guests < 0 or guests > 10:
        raise HTTPException(status_code=422, detail="guests must be between 0 and 10")
    child = get_child_for_parent(current_user, db, child_id)
    event = db.execute(_parent_events_q(child).where(Event.id == event_id)).scalar_one_or_none()
    if not event or not event.rsvp_enabled or event.starts_at <= datetime.datetime.now():
        raise HTTPException(status_code=404, detail="Event not found or does not take RSVPs")
    rsvp = db.execute(select(Rsvp).where(Rsvp.event_id == event.id, Rsvp.parent_user_id == current_user.sub,
                                         Rsvp.college_id == current_user.college_id)).scalar_one_or_none()
    if rsvp:
        rsvp.status, rsvp.guests, rsvp.student_id = status_, guests, child.id
    else:
        rsvp = Rsvp(id=f"rsvp_{uuid.uuid4().hex[:16]}", college_id=current_user.college_id, event_id=event.id,
                    parent_user_id=current_user.sub, student_id=child.id, status=status_, guests=guests)
        db.add(rsvp)
    record_audit(db, current_user, "event.rsvp", "event", event.id, {"status": status_, "guests": guests})
    return rsvp


def next_demo_day_for_parent(db: Session, current_user: TokenPayload, child: Student, lang: str = "en") -> Optional[dict]:
    """The next upcoming event that takes RSVPs for this child (a demo day first), with this parent's own answer."""
    upcoming = db.execute(_parent_events_q(child).where(Event.rsvp_enabled.is_(True), Event.starts_at > datetime.datetime.now())
                          .order_by(Event.starts_at)).scalars().all()
    event = next((e for e in upcoming if e.kind == "demo_day"), upcoming[0] if upcoming else None)
    if event is None:
        return None
    mine = db.execute(select(Rsvp).where(Rsvp.event_id == event.id, Rsvp.parent_user_id == current_user.sub,
                                         Rsvp.college_id == current_user.college_id)).scalar_one_or_none()
    ta = lang == "ta"
    when = event.starts_at.strftime("%a, %b %d · %I:%M %p") + (f" – {event.ends_at.strftime('%I:%M %p')}" if event.ends_at else "")
    return {
        "id": event.id,
        "title": (event.title_ta if ta and event.title_ta else event.title_en),
        "event_date": when,
        "venue": event.location or "",
        "description": (event.description_ta if ta and event.description_ta else event.description_en) or "",
        # the web card speaks attending / declined; the RSVP table stores yes / no / maybe
        "rsvp_status": {"yes": "attending", "no": "declined", "maybe": "maybe"}.get(mine.status, "none") if mine else "none",
        "guest_count": mine.guests if mine else 1,
    }
