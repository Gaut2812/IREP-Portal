"""Screen 36 seed: Priya's two submitted rounds (PDF 7: #1 3.0, #2 3.8 with the
rubric and feedback), timestamped comments, and three open slots anchored to
the coming days. Every seed restores this demo state for Priya."""
import datetime
import uuid

from sqlalchemy import select, delete

from models.schema import Interview, InterviewSlot, InterviewBooking, InterviewRubricScore, InterviewComment
from services.interviews import rubric_config

PRIYA = "std_priya_01"
ARUN = "trn_arun_01"
ROUND1 = {"problem_solving": 3, "coding": 3, "thinking_aloud": 3, "core_cs": 3, "project": 3, "communication": 3}
ROUND2 = {"problem_solving": 4, "coding": 4, "thinking_aloud": 3, "core_cs": 4, "project": 4, "communication": 3}
FEEDBACK_EN = "Strong on DSA and explained the ML project well. Pause less before speaking, and state your approach before coding. Revise OS memory management."
FEEDBACK_TA = "DSA-வில் வலுவாக உள்ளீர்கள், ML புராஜெக்ட்டை நன்றாக விளக்கினீர்கள். பேசும் முன் இடைவெளியைக் குறைத்து, கோடிங்கிற்கு முன் உங்கள் அணுகுமுறையைச் சொல்லுங்கள். OS நினைவக மேலாண்மையை மீண்டும் படியுங்கள்."
COMMENTS = [
    (95, "Good: restated the problem and asked about edge cases first."),
    (540, "Long silence here. Say your approach out loud before typing."),
    (1210, "Clean Union-Find with path compression. State O(E · α(n)) without being asked."),
    (1980, "Project explanation was clear; add the metric you improved."),
    (2260, "OS question: revise paging vs segmentation."),
]


def _next(today: datetime.date, weekday: int, min_days: int = 1) -> datetime.date:
    d = today + datetime.timedelta(days=min_days)
    while d.weekday() != weekday:
        d += datetime.timedelta(days=1)
    return d


def seed_screen36(db, college_id: str = "col_demo_001") -> None:
    rubric_config(db, college_id)
    now = datetime.datetime.now()
    today = now.date()

    # restore Priya's demo state: remove rounds and bookings made by tests or demos
    extra = db.execute(select(Interview.id).where(Interview.student_id == PRIYA, Interview.id.notin_(["iv_priya_1", "iv_priya_2"]))).scalars().all()
    db.execute(delete(InterviewBooking).where(InterviewBooking.student_id == PRIYA))
    db.execute(delete(InterviewComment).where(InterviewComment.interview_id.in_(extra or ["_"])))
    db.execute(delete(InterviewRubricScore).where(InterviewRubricScore.interview_id.in_(extra or ["_"])))
    db.execute(delete(Interview).where(Interview.id.in_(extra or ["_"])))
    db.flush()

    for iid, n, scores, overall, days_ago, fb_en, fb_ta in [
        ("iv_priya_1", 1, ROUND1, 3.0, 30, "Good fundamentals. Practise thinking aloud and timing.", "அடிப்படைகள் நன்று. உரக்கச் சிந்தித்தல் மற்றும் நேர மேலாண்மையைப் பயிற்சி செய்யுங்கள்."),
        ("iv_priya_2", 2, ROUND2, 3.8, 9, FEEDBACK_EN, FEEDBACK_TA),
    ]:
        existing = db.execute(select(Interview).filter_by(id=iid)).scalar_one_or_none()
        if existing:
            existing.overall_score = overall
            continue
        at = datetime.datetime.combine(today - datetime.timedelta(days=days_ago), datetime.time(16, 0))
        db.add(Interview(id=iid, college_id=college_id, student_id=PRIYA, trainer_id=ARUN, round_number=n, round_type="technical",
                         scheduled_at=at, duration_min=40, status="submitted", overall_score=overall,
                         feedback_en=fb_en, feedback_ta=fb_ta, recording_key=f"recordings/interviews/priya_round{n}.mp4",
                         recording_started_at=at, submitted_at=at + datetime.timedelta(hours=2)))
        db.flush()
        for k, v in scores.items():
            db.add(InterviewRubricScore(id=f"rs_{iid}_{k}"[:64], college_id=college_id, interview_id=iid, criterion_key=k, score=v))
        if n == 2:
            for sec, text in COMMENTS:
                db.add(InterviewComment(id=f"ic_{iid}_{sec}", college_id=college_id, interview_id=iid, at_seconds=sec, text=text, author_name="Arun Kumar"))

    # PDF 7 "Book next slot": Wed 4:00 PM Technical · Sat 10:30 AM HR · Sat 12:00 PM AI-allowed coding
    wed = _next(today, 2, 1)
    sat = _next(today, 5, 2)
    plan = [("slot_demo_tech", wed, 16, 0, "technical"), ("slot_demo_hr", sat, 10, 30, "hr"), ("slot_demo_ai", sat, 12, 0, "ai_coding")]
    db.execute(delete(InterviewSlot).where(InterviewSlot.trainer_id == ARUN, InterviewSlot.id.notin_([p[0] for p in plan]),
                                           InterviewSlot.starts_at > now))
    for sid, day, hh, mm, rtype in plan:
        start = datetime.datetime(day.year, day.month, day.day, hh, mm)
        slot = db.execute(select(InterviewSlot).filter_by(id=sid)).scalar_one_or_none()
        if not slot:
            slot = InterviewSlot(id=sid, college_id=college_id, trainer_id=ARUN, batch_id="bat_aids_s5_aids", round_type=rtype,
                                 starts_at=start, duration_min=40, status="open")
            db.add(slot)
        slot.starts_at, slot.status = start, "open"
    db.flush()
