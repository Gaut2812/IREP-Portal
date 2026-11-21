"""Leave (screens 10 and 43). Release rule: a leave request changes attendance
only after a trainer approves it. Approved leave turns the student's absences
in the range into 'Excused'; Present and trainer overrides are never touched."""
import datetime
from typing import Dict

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.schema import LeaveRequest, SessionAttendance, SessionItem, Student


def covered_by_leave(db: Session, student_id: str, day: datetime.date) -> bool:
    return db.execute(select(LeaveRequest.id).where(
        LeaveRequest.student_id == student_id, LeaveRequest.status == "approved",
        LeaveRequest.start_date <= day, LeaveRequest.end_date >= day)).first() is not None


def apply_approved_leave(db: Session, leave: LeaveRequest, now: datetime.datetime) -> Dict[str, int]:
    """Mark the student's sessions in the range Excused (already-ended ones; later
    ones are finalized as Excused by services/live_class.finalize_session)."""
    st = db.get(Student, leave.student_id)
    start = datetime.datetime.combine(leave.start_date, datetime.time.min)
    end = datetime.datetime.combine(leave.end_date + datetime.timedelta(days=1), datetime.time.min)
    sessions = db.execute(select(SessionItem).where(
        SessionItem.batch_id == st.batch_id, SessionItem.college_id == st.college_id, SessionItem.status != "Cancelled",
        SessionItem.scheduled_start >= start, SessionItem.scheduled_start < end, SessionItem.scheduled_end <= now)).scalars().all()
    excused = kept = 0
    for s in sessions:
        row = db.execute(select(SessionAttendance).where(SessionAttendance.session_id == s.id,
                                                         SessionAttendance.student_id == st.id)).scalar_one_or_none()
        if row and (row.status == "Present" or row.source == "manual"):
            kept += 1
            continue
        if row is None:
            row = SessionAttendance(id=("att_" + s.id + "_" + st.id)[:64], college_id=s.college_id, session_id=s.id,
                                    student_id=st.id, minutes_present=0)
            db.add(row)
        row.status, row.source, row.marked_at = "Excused", "leave", now
        excused += 1
    return {"excused": excused, "kept": kept}
