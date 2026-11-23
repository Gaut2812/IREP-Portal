"""Screen 45 seed: the demo IREP staff account and the demo college's MoU.
Idempotent; dates are relative to today. Colleges created by tests or demos
(anything but the demo college) are left alone."""
import datetime

from sqlalchemy import select

from core.security import PLATFORM_TENANT, get_password_hash
from models.schema import College, MouTerm, User

STAFF_ID = "usr_irep_staff_01"
SUPER_ID = "usr_irep_super_01"
FEATURES = {"virtual_labs": True, "cyber_range": True, "ai_study_buddy": True, "parent_sms": True,
            "whatsapp": False, "teams_live_classes": True}


def seed_screen45(db, college_id: str = "col_demo_001") -> None:
    if db.get(User, STAFF_ID) is None:
        db.add(User(id=STAFF_ID, college_id=PLATFORM_TENANT, email="staff@irep.demo", hashed_password=get_password_hash("password123"),
                    role="irep_admin", name="IREP Operations", phone="9876500001", avatar_initials="IO", language_pref="en"))
    if db.get(User, SUPER_ID) is None:
        db.add(User(id=SUPER_ID, college_id=PLATFORM_TENANT, email="super@irep.demo", hashed_password=get_password_hash("password123"),
                    role="super_admin", name="IREP Director", phone="9876500002", avatar_initials="ID", language_pref="en"))
    else:                                               # a re-run restores demo state
        s = db.get(User, SUPER_ID)
        s.role, s.is_active = "super_admin", True
    staff = db.get(User, STAFF_ID)
    if staff is not None:
        staff.role, staff.is_active = "irep_admin", True
    c = db.get(College, college_id)
    if c is None:
        return
    c.city, c.state, c.status = c.city or "Coimbatore", c.state or "Tamil Nadu", "active"
    c.features = {**FEATURES, **(c.features or {})} if c.features else dict(FEATURES)
    today = datetime.date.today()
    m = db.get(MouTerm, "mou_demo_2026")
    if m is None:
        db.add(MouTerm(id="mou_demo_2026", college_id=college_id, starts_on=today.replace(month=6, day=1) if today.month >= 6 else today.replace(year=today.year - 1, month=6, day=1),
                       ends_on=(today.replace(month=5, day=31) if today.month < 6 else today.replace(year=today.year + 1, month=5, day=31)),
                       students_cap=650, lab_hours_per_student=60, ai_calls_per_day=30, storage_gb=200, fee_per_student_inr=4500,
                       status="active", notes="Academic year MoU (B.Tech Sem 2-7)", created_by=STAFF_ID))
    db.flush()
    m = db.get(MouTerm, "mou_demo_2026")
    m.lab_overage_inr_per_hour, m.storage_overage_inr_per_gb = 25, 10       # S16 billing: agreed overage rates
    _seed_billing(db, college_id)


def _seed_billing(db, college_id: str) -> None:
    """S16: the demo college starts with no invoices and one credit of Rs 5,000 (re-run restores this)."""
    from sqlalchemy import delete, select
    from models.schema import BillingCredit, Invoice, InvoiceLine
    ids = list(db.execute(select(Invoice.id).where(Invoice.college_id == college_id)).scalars())
    db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id.in_(ids or ["_"])))
    db.execute(delete(Invoice).where(Invoice.id.in_(ids or ["_"])))
    db.execute(delete(BillingCredit).where(BillingCredit.college_id == college_id))
    db.flush()
    db.add(BillingCredit(id="cred_demo_welcome", college_id=college_id, amount_paise=500_000, used_paise=0,
                         reason="Pilot welcome credit", created_by=SUPER_ID))
    db.flush()
