"""Screen 08 seed: recordings for past batch sessions and a library of older
recordings; the weekly session calendar is re-anchored to today on every run."""
import datetime

from sqlalchemy import select

import random

from models.schema import Recording, RecordingView, SessionItem, SessionAttendance, Student
from services.live_sessions import rebase_week_sessions, WEEK_PLAN

HISTORY_WEEKS = 9
# Priya's misses in earlier weeks: (weeks back, weekday). 4 misses -> ~92% semester attendance
PRIYA_HISTORY_MISSES = {(2, 1), (4, 3), (6, 5), (8, 2)}
PRIYA_WATCHED = {(2, 1), (4, 3), (6, 5)}   # watched the recording for 3 of those

BATCH = "bat_aids_s5_aids"
SESSION_RECORDINGS = [
    ("rec_mon_unionfind", "sess_mon_unionfind", "DSA: Union-Find drill", "recordings/aids-s5/dsa_union_find.mp4", 58),
    ("rec_tue_model_eval", "sess_tue_model_eval", "Track: Model evaluation lab", "recordings/aids-s5/model_eval.mp4", 62),
    ("rec_wed_aptitude", "sess_wed_aptitude", "Aptitude: Data interpretation", "recordings/aids-s5/data_interpretation.mp4", 54),
]
LIBRARY = [
    ("rec_cloud_deploy", "Cloud deploy walkthrough", "recordings/library/cloud_deploy.mp4", 58, 21),
    ("rec_docker_compose", "Docker Compose lab", "recordings/library/docker_compose_lab.mp4", 171, 28),
    ("rec_mock_tips", "Mock interview tips", "recordings/library/mock_interview_tips.mp4", 42, 35),
]


def _chapters(minutes: int):
    step = max(5, minutes // 4)
    names = ["Introduction", "Concept walkthrough", "Hands-on demo", "Q&A and recap"]
    return [{"at_sec": i * step * 60, "title": n} for i, n in enumerate(names)]


def seed_history(db, college_id: str = "col_demo_001") -> int:
    """Past weeks for the AI & DS Sem 5 batch, so semester attendance is computed from rows."""
    if db.execute(select(SessionItem).where(SessionItem.id.like("sess_hist_%"))).first():
        return 0
    rng = random.Random(1408)
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    students = db.execute(select(Student).filter_by(batch_id=BATCH, college_id=college_id)).scalars().all()
    created = 0
    for k in range(1, HISTORY_WEEKS + 1):
        wk_monday = monday - datetime.timedelta(days=7 * k)
        for sid, wd, (hh, mm), minutes, title, stype, lab in WEEK_PLAN:
            day = wk_monday + datetime.timedelta(days=wd)
            start = datetime.datetime(day.year, day.month, day.day, hh, mm)
            hid = f"sess_hist_w{k}_{wd}"
            db.add(SessionItem(id=hid, college_id=college_id, title=title, track="AI & DS", trainer_name="Arun K.",
                               scheduled_start=start, scheduled_end=start + datetime.timedelta(minutes=minutes),
                               duration_min=minutes, session_type=stype, status="Completed", batch_id=BATCH,
                               week_no=max(1, 8 - k)))
            db.flush()
            db.add(Recording(id=f"rec_hist_w{k}_{wd}", college_id=college_id, session_id=hid, batch_id=BATCH, title=title,
                             storage_key=f"recordings/aids-s5/w{k}_{wd}.mp4", duration_min=minutes, chapters=_chapters(minutes),
                             has_transcript=True, has_summary=True, recorded_on=day, status="ready"))
            db.flush()
            for st in students:
                if st.id == "std_priya_01":
                    present = (k, wd) not in PRIYA_HISTORY_MISSES
                else:
                    present = rng.random() * 100 < st.attendance_pct
                db.add(SessionAttendance(id=f"att_{hid}_{st.id}"[:64], college_id=college_id, session_id=hid, student_id=st.id,
                                         minutes_present=minutes if present else rng.randint(0, minutes // 2),
                                         status="Present" if present else "Absent", marked_at=start + datetime.timedelta(minutes=minutes)))
            created += 1
    db.flush()
    for k, wd in PRIYA_WATCHED:
        db.add(RecordingView(id=f"rv_priya_w{k}_{wd}", college_id=college_id, student_id="std_priya_01",
                             recording_id=f"rec_hist_w{k}_{wd}", watched_seconds=3000, completed=True))
    db.flush()
    return created


def seed_screen08(db, college_id: str = "col_demo_001") -> int:
    rebase_week_sessions(db, college_id)
    seed_history(db, college_id)
    created = 0
    today = datetime.date.today()
    for rid, sid, title, key, minutes in SESSION_RECORDINGS:
        if db.execute(select(Recording).filter_by(id=rid)).first():
            continue
        db.add(Recording(id=rid, college_id=college_id, session_id=sid, batch_id=BATCH, title=title, storage_key=key,
                         duration_min=minutes, chapters=_chapters(minutes), has_transcript=True, has_summary=True,
                         recorded_on=today, status="ready"))
        created += 1
    for rid, title, key, minutes, days_ago in LIBRARY:
        if db.execute(select(Recording).filter_by(id=rid)).first():
            continue
        db.add(Recording(id=rid, college_id=college_id, session_id=None, batch_id=BATCH, title=title, storage_key=key,
                         duration_min=minutes, chapters=_chapters(minutes), has_transcript=True, has_summary=True,
                         recorded_on=today - datetime.timedelta(days=days_ago), status="ready"))
        created += 1
    db.flush()
    return created
