"""S15 seed (screens 37, 38, 39): two mock drives on the demo AI & DS Sem 5 batch.

- "Mock drive: service-company pattern" ran 5 days ago and is published: an aptitude test round
  (cut-off 60 %) and a technical interview round with Arun (4 slots, cut-off 3.5). Four students took
  part; three interviews are scored and one waits on Arun's screen 37 ("to score", marked with the drive).
- "Mock drive: product-company pattern" is a draft 9 days ahead with a test and an interview round.

Idempotent and deterministic: fixed ids, dates relative to today; a re-run restores this state.
"""
import datetime

from sqlalchemy import delete, select

from models.schema import (DriveRound, Event, Interview, InterviewBooking, InterviewComment, InterviewRubricScore,
                           InterviewSlot, MockDrive, PracticeTest, Student, TestAttempt)
from services.interviews import rubric_config

BATCH = "bat_aids_s5_aids"
ARUN = "trn_arun_01"
TEST = "test_service_aptitude"
DONE_EVENT, DONE_DRIVE = "evt_drive_service", "drv_demo_service"
NEXT_EVENT, NEXT_DRIVE = "evt_drive_product", "drv_demo_product"
# per participant: (test score out of 30, interview overall or None = not scored yet)
RESULTS = [(24, 4.1), (21, 3.6), (15, 3.9), (19, None)]


def _event(db, eid, college_id, title_en, title_ta, starts_at, status):
    e = db.get(Event, eid)
    if e is None:
        e = Event(id=eid, college_id=college_id, title_en=title_en, kind="drive")
        db.add(e)
    e.title_en, e.title_ta, e.kind, e.starts_at = title_en, title_ta, "drive", starts_at
    e.ends_at = starts_at + datetime.timedelta(hours=6)
    e.audience, e.batch_id, e.location, e.rsvp_enabled, e.status = "students", BATCH, "Placement cell, Block B", True, status
    e.description_en = "Company-pattern mock drive: an aptitude test, then a technical interview."
    e.description_ta = "நிறுவன முறை மாதிரி முகாம்: திறனறிவுத் தேர்வு, பின் தொழில்நுட்ப நேர்காணல்."
    e.published_at = starts_at - datetime.timedelta(days=7) if status == "published" else None
    return e


def _drive(db, did, eid, college_id, pattern, status, published_at):
    d = db.get(MockDrive, did)
    if d is None:
        d = MockDrive(id=did, college_id=college_id, event_id=eid)
        db.add(d)
    d.batch_id, d.company_pattern, d.status, d.published_at, d.results_published_at = BATCH, pattern, status, published_at, None
    return d


def _round(db, rid, did, college_id, no, kind, **kw):
    r = db.get(DriveRound, rid)
    if r is None:
        r = DriveRound(id=rid, college_id=college_id, drive_id=did, round_no=no, kind=kind)
        db.add(r)
    r.round_no, r.kind = no, kind
    for k, v in {"test_id": None, "round_type": None, "trainer_id": None, "starts_at": None, "duration_min": 40,
                 "slot_count": 0, "cutoff": 0, **kw}.items():
        setattr(r, k, v)
    return r


def seed_screen38(db, college_id: str = "col_demo_001") -> None:
    if db.get(PracticeTest, TEST) is None or not db.execute(select(Student.id).where(Student.batch_id == BATCH)).first():
        return
    cfg = rubric_config(db, college_id)
    now = datetime.datetime.now()
    today = now.date()
    done_at = datetime.datetime.combine(today - datetime.timedelta(days=5), datetime.time(10, 0))
    next_at = datetime.datetime.combine(today + datetime.timedelta(days=9), datetime.time(10, 0))

    _event(db, DONE_EVENT, college_id, "Mock drive: service-company pattern", "மாதிரி முகாம்: சேவை நிறுவன முறை", done_at, "published")
    _event(db, NEXT_EVENT, college_id, "Mock drive: product-company pattern", "மாதிரி முகாம்: தயாரிப்பு நிறுவன முறை", next_at, "draft")
    db.flush()
    _drive(db, DONE_DRIVE, DONE_EVENT, college_id, "Service company: aptitude + technical", "published", done_at - datetime.timedelta(days=7))
    _drive(db, NEXT_DRIVE, NEXT_EVENT, college_id, "Product company: aptitude + coding interview", "draft", None)
    db.flush()

    # rounds (drafts keep exactly their seeded rounds)
    keep = ["drr_service_1", "drr_service_2", "drr_product_1", "drr_product_2"]
    stale = db.execute(select(DriveRound.id).where(DriveRound.drive_id.in_([DONE_DRIVE, NEXT_DRIVE]), DriveRound.id.notin_(keep))).scalars().all()
    if stale:
        db.execute(delete(InterviewSlot).where(InterviewSlot.drive_round_id.in_(stale), InterviewSlot.status != "booked"))
        db.execute(delete(DriveRound).where(DriveRound.id.in_(stale)))
    _round(db, "drr_service_1", DONE_DRIVE, college_id, 1, "test", test_id=TEST, cutoff=60)
    _round(db, "drr_service_2", DONE_DRIVE, college_id, 2, "interview", round_type="technical", trainer_id=ARUN,
           starts_at=done_at + datetime.timedelta(hours=2), duration_min=40, slot_count=len(RESULTS), cutoff=3.5)
    _round(db, "drr_product_1", NEXT_DRIVE, college_id, 1, "test", test_id=TEST, cutoff=70)
    _round(db, "drr_product_2", NEXT_DRIVE, college_id, 2, "interview", round_type="ai_coding", trainer_id=ARUN,
           starts_at=next_at + datetime.timedelta(hours=2), duration_min=40, slot_count=3, cutoff=4.0)
    t = db.get(PracticeTest, TEST)
    if BATCH not in (t.batch_ids or []):
        t.batch_ids = list(t.batch_ids or []) + [BATCH]
    db.flush()

    # participants: the first four students of the batch by register number (not Priya: screen 36 owns her)
    students = db.execute(select(Student).where(Student.batch_id == BATCH, Student.id != "std_priya_01")
                          .order_by(Student.register_no).limit(len(RESULTS))).scalars().all()
    keys = [c["key"] for c in cfg.criteria]
    for i, (st, (test_score, overall)) in enumerate(zip(students, RESULTS), start=1):
        aid = f"ta_drive_service_{i}"
        a = db.get(TestAttempt, aid)
        start = done_at - datetime.timedelta(minutes=40)
        if a is None:
            a = TestAttempt(id=aid, college_id=college_id, test_id=TEST, student_id=st.id, ends_at=start + datetime.timedelta(minutes=30))
            db.add(a)
        a.student_id, a.status, a.started_at, a.submitted_at = st.id, "submitted", start, start + datetime.timedelta(minutes=28)
        a.score, a.total_questions, a.accuracy_pct, a.time_taken_sec = test_score, 30, round(100 * test_score / 30, 1), 28 * 60

        sid, bid, iid = f"slot_drive_service_{i}", f"bk_drive_service_{i}", f"iv_drive_service_{i}"
        at = done_at + datetime.timedelta(hours=2, minutes=40 * (i - 1))
        slot = db.get(InterviewSlot, sid)
        if slot is None:
            slot = InterviewSlot(id=sid, college_id=college_id, trainer_id=ARUN)
            db.add(slot)
        slot.batch_id, slot.round_type, slot.starts_at, slot.duration_min = BATCH, "technical", at, 40
        slot.status, slot.drive_round_id = "booked", "drr_service_2"
        db.flush()
        db.execute(delete(InterviewRubricScore).where(InterviewRubricScore.interview_id == iid))
        db.execute(delete(InterviewComment).where(InterviewComment.interview_id == iid))
        iv = db.get(Interview, iid)
        if iv is None:
            iv = Interview(id=iid, college_id=college_id, student_id=st.id, slot_id=sid, scheduled_at=at)
            db.add(iv)
        iv.student_id, iv.trainer_id, iv.slot_id, iv.round_number, iv.round_type = st.id, ARUN, sid, 1, "technical"
        iv.scheduled_at, iv.duration_min, iv.recording_key = at, 40, None
        if overall is None:                                        # waits on Arun's screen 37
            iv.status, iv.overall_score, iv.feedback_en, iv.feedback_ta, iv.submitted_at = "scheduled", None, None, None, None
        else:
            iv.status, iv.overall_score, iv.submitted_at = "submitted", overall, at + datetime.timedelta(hours=1)
            iv.feedback_en = "Clear approach and clean code; practise explaining trade-offs."
            iv.feedback_ta = "தெளிவான அணுகுமுறை, சுத்தமான கோடு; மாற்று வழிகளின் நன்மை தீமைகளை விளக்கப் பழகுங்கள்."
            db.flush()
            for k in keys:
                db.add(InterviewRubricScore(id=f"rs_{iid}_{k}"[:64], college_id=college_id, interview_id=iid, criterion_key=k,
                                            score=max(1, min(cfg.max_score, round(overall)))))
        b = db.execute(select(InterviewBooking).where(InterviewBooking.slot_id == sid)).scalar_one_or_none()
        if b is None:
            db.add(InterviewBooking(id=bid, college_id=college_id, slot_id=sid, student_id=st.id, interview_id=iid))
        else:
            b.student_id, b.interview_id = st.id, iid
    db.flush()
