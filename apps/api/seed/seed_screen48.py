"""Screen 48 seed: granted parent-data consent for every demo parent-child
link (so screens 15/16/18 show data) and public-portfolio consent for the
demo student. Re-seeding restores this state: consent rows and data
requests created by tests or demos in the demo college are removed."""
import datetime

from sqlalchemy import delete, select

from models.schema import ConsentRecord, DataRequest, ParentStudent, RosterChangeRequest, TrainerNote


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
    for cid, (student_id, by, purpose, method) in wanted.items():
        row = db.get(ConsentRecord, cid)
        if row is None:
            db.add(ConsentRecord(id=cid, college_id=college_id, subject_student_id=student_id, granted_by_user_id=by,
                                 purpose=purpose, status="granted", method=method, recorded_at=at))
        else:
            row.status, row.recorded_at = "granted", at
    db.flush()
