"""Screen 15: parent overview assembled from rows for one child."""
import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.security import TokenPayload
from models.schema import (
    Student, Certificate, MonthlyCard, Event, Rsvp, StudentProject, SessionAttendance, SessionItem, Trainer, User, BatchTrainer,
)

BAND_TA = {"Placement Ready": "வேலைவாய்ப்புக்கு தயார்", "Nearly Ready": "கிட்டத்தட்ட தயார்", "Needs Support": "ஆதரவு தேவை"}
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MONTHS_TA = ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"]


def month_label(month: int, lang: str) -> str:
    return (MONTHS_TA if lang == "ta" else MONTHS_EN)[month - 1]


def latest_released_card(db: Session, student: Student) -> Optional[MonthlyCard]:
    return db.execute(
        select(MonthlyCard).where(
            MonthlyCard.student_id == student.id, MonthlyCard.college_id == student.college_id,
            MonthlyCard.status.in_(["approved", "sent"]),
        ).order_by(MonthlyCard.year.desc(), MonthlyCard.month.desc())
    ).scalars().first()


def child_trainers(db: Session, student: Student):
    if not student.batch_id:
        return []
    rows = db.execute(
        select(Trainer, User.name).join(User, User.id == Trainer.user_id)
        .join(BatchTrainer, BatchTrainer.trainer_id == Trainer.id)
        .where(BatchTrainer.batch_id == student.batch_id, Trainer.college_id == student.college_id)
    ).all()
    return [{"trainer_id": t.id, "user_id": t.user_id, "name": name, "designation": t.designation} for t, name in rows]


def build_parent_overview(db: Session, student: Student, child_name: str, current_user: TokenPayload, lang: str = "en",
                          today: Optional[datetime.date] = None) -> dict:
    today = today or datetime.date.today()
    college_id = student.college_id
    # Screen 48 / DPDP: nothing about the child is shown to a parent before
    # the parent-data consent is granted (or after it is withdrawn).
    from services.consent import current as consent_state
    state = consent_state(db, student.id, "parent_data_processing")
    if state != "granted":
        return {
            "consent_required": True,
            "consent_state": state or "missing",
            "ward": {"id": student.id, "name": child_name},
            "consent": {
                "purpose": "parent_data_processing",
                "title": "உங்கள் பிள்ளையின் தரவைப் பார்க்க ஒப்புதல் தேவை" if lang == "ta" else "Your consent is needed to see your child's progress",
                "body": ("வருகை, மதிப்பெண்கள், திட்டங்கள் மற்றும் பயிற்சியாளர் செய்திகளை உங்களுக்குக் காட்ட IREP உங்கள் பிள்ளையின் தரவைச் செயலாக்குகிறது. "
                         "நீங்கள் எப்போது வேண்டுமானாலும் ஒப்புதலைத் திரும்பப் பெறலாம்.") if lang == "ta" else
                        ("IREP processes your child's attendance, scores, projects and trainer messages to show them to you. "
                         "You can withdraw this consent at any time."),
            },
        }
    card = latest_released_card(db, student)

    certs = db.execute(select(Certificate).filter_by(student_id=student.id, college_id=college_id)).scalars().all()
    earned = [c for c in certs if c.status == "earned"]
    scheduled = sorted([c for c in certs if c.status == "scheduled" and c.exam_date], key=lambda c: c.exam_date)
    cert_note = ""
    if scheduled:
        short = scheduled[0].title.split(" ")[0]
        cert_note = (f"{short} தேர்வு {scheduled[0].exam_date.strftime('%b %d')}" if lang == "ta"
                     else f"{short} exam on {scheduled[0].exam_date.strftime('%b %d')}")

    projects = db.execute(
        select(StudentProject).filter_by(student_id=student.id, college_id=college_id).order_by(StudentProject.is_featured.desc())
    ).scalars().all()
    live = next((p for p in projects if p.live_demo_url), None)

    now = datetime.datetime.combine(today, datetime.time.min)
    events = db.execute(
        select(Event).where(
            Event.college_id == college_id, Event.status == "published", Event.starts_at >= now - datetime.timedelta(hours=12),
            Event.audience.in_(["parents", "all"]), Event.student_id.is_(None),
            (Event.batch_id.is_(None)) | (Event.batch_id == student.batch_id),
        ).order_by(Event.starts_at).limit(5)
    ).scalars().all()
    rsvps = {r.event_id: r for r in db.execute(
        select(Rsvp).where(Rsvp.parent_user_id == current_user.sub, Rsvp.college_id == college_id)
    ).scalars().all()}

    attended = db.execute(select(func.count(SessionAttendance.id)).where(SessionAttendance.student_id == student.id, SessionAttendance.status == "Present")).scalar_one()
    total = db.execute(select(func.count(SessionAttendance.id)).where(SessionAttendance.student_id == student.id)).scalar_one()
    good = student.attendance_pct >= 85

    def ev(e: Event):
        r = rsvps.get(e.id)
        return {
            "id": e.id, "title": e.title_ta if lang == "ta" and e.title_ta else e.title_en, "kind": e.kind,
            "when": e.starts_at.strftime("%a, %b %d · %I:%M %p").replace(" 0", " "), "date": e.starts_at.strftime("%b %d"),
            "starts_at": e.starts_at.isoformat(), "location": e.location,
            "description": e.description_ta if lang == "ta" and e.description_ta else e.description_en,
            "rsvp_enabled": e.rsvp_enabled, "rsvp_status": r.status if r else None, "guests": r.guests if r else 0,
        }

    # L31: open flags the trainer has raised with the parent show as support alerts
    from models.schema import AtRiskFlag
    from services.at_risk import ACTION_LABEL, reason_text
    lg = "ta" if lang == "ta" else "en"
    alerts = [{"id": f.id, "issue": reason_text(f.reason_key, f.reason_text, lg), "next_step": ACTION_LABEL[f.suggested_action][lg],
               "since": (f.parent_notified_at or datetime.datetime.combine(f.flagged_on, datetime.time.min)).date().isoformat()}
              for f in db.execute(select(AtRiskFlag).where(
                  AtRiskFlag.student_id == student.id, AtRiskFlag.college_id == college_id, AtRiskFlag.status != "resolved",
                  AtRiskFlag.parent_notified.is_(True)).order_by(AtRiskFlag.parent_notified_at.desc())).scalars()]

    from services.broadcasts import for_parent      # L30: announcements from the college and trainers
    announcements = [{"id": b.id, "title": b.title_ta if lang == "ta" and b.title_ta else b.title,
                      "body": b.body_ta if lang == "ta" and b.body_ta else b.body, "from": b.author_role,
                      "at": b.created_at.date().isoformat() if b.created_at else None}
                     for b in for_parent(db, college_id, student.batch_id)]

    return {
        "consent_required": False,
        "support_alerts": alerts,
        "announcements": announcements,
        "ward": {
            "id": student.id, "name": child_name, "semester": student.semester, "branch": student.branch, "track": student.track,
            "details": f"Sem {student.semester} · {student.branch}", "batch": student.batch_name, "college": "Demo Engineering College",
        },
        "kpis": {
            "readiness_score": student.readiness_score,
            "readiness_delta": student.readiness_delta,
            "readiness_band": student.readiness_band,
            "readiness_band_label": BAND_TA.get(student.readiness_band, student.readiness_band) if lang == "ta" else student.readiness_band,
            "attendance_pct": student.attendance_pct,
            "attendance_note": ("சிறப்பானது" if good else "கவனம் தேவை") if lang == "ta" else ("Excellent" if good else "Needs attention"),
            "attendance_good": good,
            "sessions_attended": attended, "sessions_total": total,
            "problems_solved": student.problems_solved,
            "certifications": len(earned), "cert_note": cert_note,
        },
        "monthly_card": {
            "id": card.id, "month": month_label(card.month, lang), "month_num": card.month, "year": card.year,
            "prev_month": month_label(card.month - 1 if card.month > 1 else 12, lang),
            "rows": [
                {"area": r.get("area_ta") if lang == "ta" and r.get("area_ta") else r.get("area_en"),
                 "prev": r.get("prev_ta") if lang == "ta" and r.get("prev_ta") else r.get("prev"),
                 "curr": r.get("curr_ta") if lang == "ta" and r.get("curr_ta") else r.get("curr"),
                 "status": r.get("status_ta") if lang == "ta" and r.get("status_ta") else r.get("status_en"),
                 "color": r.get("color", "green")}
                for r in (card.rows or [])
            ],
            "how_to_help": card.how_to_help_ta if lang == "ta" and card.how_to_help_ta else card.how_to_help_en,
            "trainer_remark": card.trainer_remark_ta if lang == "ta" and card.trainer_remark_ta else card.trainer_remark_en,
            "trainer_name": card.trainer_name, "status": card.status,
            "released_at": (card.sent_at or card.approved_at).isoformat() if (card.sent_at or card.approved_at) else None,
        } if card else None,
        "portfolio": {
            "github_projects": len(projects),
            "live_project": live.title if live else None, "live_url": live.live_demo_url if live else None,
            "demo_video": next((f"Sem {student.semester - 1} project" for p in projects if p.category == "machine_learning"), None),
        },
        "upcoming": [ev(e) for e in events],
        "trainers": child_trainers(db, student),
        "reply_promise_hours": 24,
    }
