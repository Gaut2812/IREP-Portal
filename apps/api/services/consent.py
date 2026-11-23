"""Consent records (screen 48; DPDP). Append-only: the latest row per
(student, purpose) is the current state. Parent-facing data for a student
needs a granted `parent_data_processing` consent (docs/screens/48)."""
import datetime
import uuid
from typing import Dict, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.schema import ConsentRecord

PURPOSES = ("parent_data_processing", "public_portfolio", "ai_hints", "recordings", "sms_alerts")
METHODS = ("otp_parent", "paper_form_upload", "in_app")


def current(db: Session, student_id: str, purpose: str) -> Optional[str]:
    """'granted', 'withdrawn' or None (never asked)."""
    row = db.execute(select(ConsentRecord.status).where(
        ConsentRecord.subject_student_id == student_id, ConsentRecord.purpose == purpose)
        .order_by(ConsentRecord.recorded_at.desc(), ConsentRecord.id.desc()).limit(1)).scalar_one_or_none()
    return row


def is_granted(db: Session, student_id: str, purpose: str) -> bool:
    return current(db, student_id, purpose) == "granted"


def current_for(db: Session, college_id: str, student_ids: Iterable[str]) -> Dict[str, Dict[str, str]]:
    """{student_id: {purpose: status}} for many students in one query."""
    ids = list(student_ids)
    if not ids:
        return {}
    latest = (select(ConsentRecord.subject_student_id, ConsentRecord.purpose, func.max(ConsentRecord.recorded_at).label("at"))
              .where(ConsentRecord.college_id == college_id, ConsentRecord.subject_student_id.in_(ids))
              .group_by(ConsentRecord.subject_student_id, ConsentRecord.purpose).subquery())
    rows = db.execute(select(ConsentRecord.subject_student_id, ConsentRecord.purpose, ConsentRecord.status).join(
        latest, (ConsentRecord.subject_student_id == latest.c.subject_student_id)
        & (ConsentRecord.purpose == latest.c.purpose) & (ConsentRecord.recorded_at == latest.c.at))).all()
    out: Dict[str, Dict[str, str]] = {}
    for sid, purpose, status in rows:
        out.setdefault(sid, {})[purpose] = status
    return out


def record(db: Session, *, college_id: str, student_id: str, granted_by: str, purpose: str, status: str, method: str,
           evidence_ref: Optional[str] = None, at: Optional[datetime.datetime] = None,
           notice_version: Optional[str] = None, verified_at: Optional[datetime.datetime] = None) -> ConsentRecord:
    if purpose not in PURPOSES or status not in ("granted", "withdrawn", "requested") or method not in METHODS:
        raise ValueError("invalid consent record")
    row = ConsentRecord(id=f"cns_{uuid.uuid4().hex[:20]}", college_id=college_id, subject_student_id=student_id,
                        granted_by_user_id=granted_by, purpose=purpose, status=status, method=method,
                        evidence_ref=evidence_ref, recorded_at=at or datetime.datetime.utcnow(),
                        notice_version=notice_version or NOTICES.get(purpose, {}).get("version"), verified_at=verified_at)
    db.add(row)
    return row


# ---------------------------------------------------------------- S16 DPDP: minors, notices, verifiable parental consent

ADULT_AGE = 18
# Optional purposes: for a minor they count only when a linked parent granted them (identity-bound) or
# the college recorded a signed paper form. parent_data_processing keeps its own rule (screen 15 gate).
OPTIONAL = ("public_portfolio", "ai_hints", "recordings", "sms_alerts")
PARENT_METHODS = ("otp_parent", "paper_form_upload")
IDENTITY_WINDOW = datetime.timedelta(minutes=15)       # the parent's OTP sign-in must be this recent to grant

NOTICES = {
    "parent_data_processing": {"version": "2026-11", "en": "Your child's attendance, scores, readiness, reports and certificates are shown to you, the parent, by IREP and the college.",
                               "ta": "உங்கள் குழந்தையின் வருகை, மதிப்பெண்கள், தயார்நிலை, அறிக்கைகள், சான்றிதழ்கள் பெற்றோரான உங்களுக்கு IREP மற்றும் கல்லூரியால் காட்டப்படும்."},
    "public_portfolio": {"version": "2026-11", "en": "The student's project portfolio (projects, demo links, certificates) can be shared on a public link with recruiters.",
                         "ta": "மாணவரின் திட்டப்பணி போர்ட்ஃபோலியோ (திட்டங்கள், டெமோ இணைப்புகள், சான்றிதழ்கள்) வேலைவாய்ப்பு நிறுவனங்களுடன் பொது இணைப்பில் பகிரப்படலாம்."},
    "ai_hints": {"version": "2026-11", "en": "The student's questions to the AI Study Buddy are sent to an AI service (Anthropic) to get answers. Emails and phone numbers are removed first; trainers see only counts.",
                 "ta": "AI படிப்பு நண்பரிடம் மாணவர் கேட்கும் கேள்விகள் பதில் பெற AI சேவைக்கு (Anthropic) அனுப்பப்படும். மின்னஞ்சல், கைபேசி எண்கள் முதலில் நீக்கப்படும்; பயிற்சியாளர்கள் எண்ணிக்கையை மட்டும் பார்ப்பர்."},
    "recordings": {"version": "2026-11", "en": "Live classes and mock interviews the student joins may be recorded and kept for the batch to watch again.",
                   "ta": "மாணவர் பங்கேற்கும் நேரலை வகுப்புகளும் மாதிரி நேர்காணல்களும் பதிவு செய்யப்பட்டு, தொகுதி மீண்டும் பார்க்க வைக்கப்படலாம்."},
    "sms_alerts": {"version": "2026-11", "en": "Alerts about attendance, events and support plans may be sent by SMS to the registered mobile number.",
                   "ta": "வருகை, நிகழ்வுகள், உதவித் திட்டங்கள் பற்றிய அறிவிப்புகள் பதிவு செய்த கைபேசி எண்ணுக்கு SMS மூலம் அனுப்பப்படலாம்."},
}


PARENTAL_REQUIRED = {
    "ai_hints": {"code": "parental_consent_required", "reason": "parental_consent_required",
                 "message": "A parent has to agree before you can use the AI Study Buddy, because you are under 18. Ask on My data & consent; your parent approves on their Consent page.",
                 "message_ta": "நீங்கள் 18 வயதுக்குக் குறைவானவர் என்பதால், AI படிப்பு நண்பரைப் பயன்படுத்தும் முன் பெற்றோர் ஒப்புதல் தேவை. 'என் தரவு & ஒப்புதல்' பக்கத்தில் கேளுங்கள்; பெற்றோர் தங்கள் ஒப்புதல் பக்கத்தில் ஏற்பார்."},
}


def age_on(dob: Optional[datetime.date], today: Optional[datetime.date] = None) -> Optional[int]:
    if dob is None:
        return None
    today = today or datetime.date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def is_minor(student, today: Optional[datetime.date] = None) -> bool:
    """Under 18. An unknown date of birth is treated as a minor (the safe choice until the college records it)."""
    age = age_on(getattr(student, "date_of_birth", None), today)
    return age is None or age < ADULT_AGE


def latest(db: Session, student_id: str, purpose: str) -> Optional[ConsentRecord]:
    return db.execute(select(ConsentRecord).where(ConsentRecord.subject_student_id == student_id, ConsentRecord.purpose == purpose)
                      .order_by(ConsentRecord.recorded_at.desc(), ConsentRecord.id.desc()).limit(1)).scalar_one_or_none()


def allowed(db: Session, student, purpose: str) -> bool:
    """Effective consent. For a minor, an optional purpose needs a parent's (or paper-form) grant."""
    row = latest(db, student.id, purpose)
    if row is None or row.status != "granted":
        return False
    if purpose in OPTIONAL and is_minor(student):
        return row.method in PARENT_METHODS
    return True


def identity_fresh(auth_time: Optional[int], now: Optional[datetime.datetime] = None) -> bool:
    """The parent signed in with the mobile OTP recently enough to grant (DPDP rule 10: identity-bound)."""
    if not auth_time:
        return False
    now = now or datetime.datetime.utcnow()
    return now - datetime.datetime.utcfromtimestamp(auth_time) <= IDENTITY_WINDOW
