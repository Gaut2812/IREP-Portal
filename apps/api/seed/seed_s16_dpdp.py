"""S16 DPDP seed: dates of birth and one demo minor.

- Every demo student gets a deterministic date of birth: adults by semester (Sem 2: 18, Sem 5: 20...).
- Vinoth S (AI & DS Sem 2) is 17: a minor. His parent Selvi S (mobile 9876543216) has a paper consent
  form for parent data on file, and Vinoth's request for the AI Study Buddy waits for her approval.
Idempotent; dates relative to today; a re-run restores this state.
"""
import datetime
import hashlib

from sqlalchemy import delete, select

from models.schema import ConsentRecord, ParentStudent, Student, User

MINOR = "std_aids_2_001_1654"
PARENT = "usr_selvi_01"
PARENT_PHONE = "9876543216"


def _dob(student_id: str, age: int, today: datetime.date) -> datetime.date:
    days = int(hashlib.sha256(student_id.encode()).hexdigest(), 16) % 300 + 1      # birthday already passed this year
    try:
        anchor = today.replace(year=today.year - age)
    except ValueError:                                                              # 29 Feb
        anchor = today.replace(year=today.year - age, day=28)
    return anchor - datetime.timedelta(days=days)


def seed_s16_dpdp(db, college_id: str = "col_demo_001") -> None:
    today = datetime.date.today()
    for st in db.execute(select(Student).where(Student.college_id == college_id)).scalars():
        st.date_of_birth = _dob(st.id, 17 + (max(st.semester or 2, 2) + 1) // 2, today)
    minor = db.get(Student, MINOR)
    if minor is None:
        db.flush()
        return
    if db.get(User, PARENT) is None:
        from core.security import get_password_hash
        db.add(User(id=PARENT, college_id=college_id, email="selvi.s@example.com", phone=PARENT_PHONE, role="parent",
                    name="Mrs. Selvi S", avatar_initials="SS", language_pref="ta",
                    hashed_password=get_password_hash("parent-signs-in-with-otp")))
        db.flush()
    minor.date_of_birth = _dob(MINOR, 17, today)
    link = db.execute(select(ParentStudent).where(ParentStudent.parent_user_id == PARENT, ParentStudent.student_id == MINOR)).scalar_one_or_none()
    if link is None:
        db.add(ParentStudent(id="ps_dpdp_selvi_vinoth", college_id=college_id, parent_user_id=PARENT, student_id=MINOR,
                             relationship="Mother"))
    db.execute(delete(ConsentRecord).where(ConsentRecord.subject_student_id == MINOR))
    db.flush()
    now = datetime.datetime.utcnow()
    db.add(ConsentRecord(id="cns_dpdp_vinoth_parent", college_id=college_id, subject_student_id=MINOR, granted_by_user_id=PARENT,
                         purpose="parent_data_processing", status="granted", method="paper_form_upload",
                         evidence_ref="import:FORM-DEMO-17", notice_version="2026-11", recorded_at=now - datetime.timedelta(days=20)))
    db.add(ConsentRecord(id="cns_dpdp_vinoth_ai", college_id=college_id, subject_student_id=MINOR, granted_by_user_id=minor.user_id,
                         purpose="ai_hints", status="requested", method="in_app", notice_version="2026-11",
                         recorded_at=now - datetime.timedelta(days=1)))
    db.flush()
