"""Screen 48 seed: granted parent-data consent for every demo parent-child
link (so screens 15/16/18 show data) and public-portfolio consent for the
demo student. Re-seeding restores this state: consent rows and data
requests created by tests or demos in the demo college are removed."""
import datetime

from sqlalchemy import delete, select

import re

from models.schema import (ConsentRecord, DataRequest, JoinEvent, LiveMeeting, ParentStudent, RosterChangeRequest,
                           ScheduleChangeRequest, SessionAttendance, SessionItem, TrainerNote)


def _cid(student_id: str, purpose: str) -> str:
    return f"cns_seed_{purpose[:12]}_{student_id}"[:64]


def seed_screen48(db, college_id: str = "col_demo_001") -> None:
    links = db.execute(select(ParentStudent).where(ParentStudent.college_id == college_id)).scalars().all()
    wanted = {}
    at = datetime.datetime.utcnow().replace(microsecond=0) - datetime.timedelta(days=60)
    for link in links:
        wanted[_cid(link.student_id, "parent_data_processing")] = (link.student_id, link.parent_user_id, "parent_data_processing", "otp_parent")
    wanted[_cid("std_priya_01", "public_portfolio")] = ("std_priya_01", "usr_priya_01", "public_portfolio", "in_app")

    db.execute(delete(ConsentRecord).where(ConsentRecord.college_id == college_id, ConsentRecord.id.not_in(list(wanted) or ["_"])))
    db.execute(delete(DataRequest).where(DataRequest.college_id == college_id))
    # screen 04 demo hygiene: roster requests and trainer notes left by tests or demos
    db.execute(delete(RosterChangeRequest).where(RosterChangeRequest.college_id == college_id))
    db.execute(delete(TrainerNote).where(TrainerNote.college_id == college_id))
    # screens 05/06: schedule requests and the sessions their approvals created (ids sess_<16 hex>)
    db.execute(delete(ScheduleChangeRequest).where(ScheduleChangeRequest.college_id == college_id))
    made = [i for i in db.execute(select(SessionItem.id).where(SessionItem.college_id == college_id)).scalars()
            if re.fullmatch(r"sess_[0-9a-f]{16}", i)]
    if made:
        for model in (JoinEvent, SessionAttendance, LiveMeeting):
            db.execute(delete(model).where(model.session_id.in_(made)))
        db.execute(delete(SessionItem).where(SessionItem.id.in_(made)))
    for s in db.execute(select(SessionItem).where(SessionItem.college_id == college_id, SessionItem.status == "Cancelled")).scalars():
        s.status = "Scheduled"            # a seeded class cancelled by a demo comes back
    for cid, (student_id, by, purpose, method) in wanted.items():
        row = db.get(ConsentRecord, cid)
        if row is None:
            db.add(ConsentRecord(id=cid, college_id=college_id, subject_student_id=student_id, granted_by_user_id=by,
                                 purpose=purpose, status="granted", method=method, recorded_at=at))
        else:
            row.status, row.recorded_at = "granted", at
    db.flush()
