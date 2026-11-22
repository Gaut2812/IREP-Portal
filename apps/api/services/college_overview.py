"""Screen 19: college overview aggregated by SQL from cohort rows."""
import datetime
from typing import Optional

from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from models.schema import Student, Branch, Certificate, Internship, Event, ReportRun, ReadinessSnapshot
from services.readiness import get_config

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_TA = ["ஜன", "பிப்", "மார்", "ஏப்", "மே", "ஜூன்", "ஜூலை", "ஆக", "செப்", "அக்", "நவ", "டிச"]
BAND_TA = {"Placement Ready": "வேலைவாய்ப்புக்கு தயார்", "Nearly Ready": "கிட்டத்தட்ட தயார்", "Needs Support": "ஆதரவு தேவை"}


def build_college_overview(db: Session, college_id: str, semester: Optional[int] = None, lang: str = "en",
                           today: Optional[datetime.date] = None) -> dict:
    today = today or datetime.date.today()
    cfg = get_config(db, college_id)

    def scoped(q):
        q = q.where(Student.college_id == college_id)
        if semester:
            q = q.where(Student.semester == semester)
        return q

    total = db.execute(scoped(select(func.count(Student.id)))).scalar_one()
    sem_min, sem_max = db.execute(scoped(select(func.min(Student.semester), func.max(Student.semester)))).one()
    branch_count = db.execute(scoped(select(func.count(func.distinct(Student.branch_id))))).scalar_one()
    avg_att = db.execute(scoped(select(func.avg(Student.attendance_pct)))).scalar_one()
    avg_att = int(round(avg_att)) if avg_att is not None else 0

    # Band distribution
    bands = db.execute(scoped(select(Student.readiness_band, func.count(Student.id))).group_by(Student.readiness_band)).all()
    band_counts = {b: c for b, c in bands}
    order = ["Placement Ready", "Nearly Ready", "Needs Support"]
    colors = {"Placement Ready": "green", "Nearly Ready": "amber", "Needs Support": "red"}
    distribution = [
        {"band": b, "label": BAND_TA[b] if lang == "ta" else b, "count": band_counts.get(b, 0),
         "percentage": int(round(band_counts.get(b, 0) * 100 / total)) if total else 0, "color": colors[b]}
        for b in order
    ]

    # Branch table with trend = avg(current snapshot) - avg(previous snapshot)
    branch_rows = db.execute(
        scoped(select(Branch.id, Branch.name, func.count(Student.id), func.avg(Student.attendance_pct), func.avg(Student.readiness_score))
               .join(Student, Student.branch_id == Branch.id)).group_by(Branch.id, Branch.name).order_by(func.count(Student.id).desc())
    ).all()
    trend_rows = db.execute(
        scoped(select(Student.branch_id, func.avg(Student.readiness_delta))).group_by(Student.branch_id)
    ).all()
    trend = {bid: round(v or 0) for bid, v in trend_rows}
    branches = [
        {"branch_id": bid, "branch": name, "students": n, "attendance": int(round(att or 0)), "avg_score": int(round(score or 0)), "trend": trend.get(bid, 0)}
        for bid, name, n, att, score in branch_rows
    ]

    # Certifications: earned total (college-wide, optionally semester-scoped via student) and cumulative by month
    cert_q = select(Certificate).join(Student, Student.id == Certificate.student_id).where(
        Certificate.college_id == college_id, Certificate.status == "earned"
    )
    if semester:
        cert_q = cert_q.where(Student.semester == semester)
    certs = db.execute(cert_q).scalars().all()
    by_month = {}
    for c in certs:
        if c.issued_on:
            by_month[(c.issued_on.year, c.issued_on.month)] = by_month.get((c.issued_on.year, c.issued_on.month), 0) + 1
    cumulative = []
    running = 0
    for key in sorted(by_month):
        running += by_month[key]
        label = (MONTHS_TA if lang == "ta" else MONTHS)[key[1] - 1]
        cumulative.append({"month": label, "year": key[0], "count": running, "new": by_month[key]})
    this_sem_start = datetime.date(today.year, 6, 1) if today.month >= 6 else datetime.date(today.year, 1, 1)
    certs_this_sem = len([c for c in certs if c.issued_on and c.issued_on >= this_sem_start and c.issued_on.month >= 9])

    # Internships
    intern_q = select(func.count(Internship.id)).join(Student, Student.id == Internship.student_id).where(Internship.college_id == college_id)
    sem6_total = db.execute(select(func.count(Student.id)).where(Student.college_id == college_id, Student.semester == 6)).scalar_one()
    if semester:
        intern_q = intern_q.where(Student.semester == semester)
    internships = db.execute(intern_q).scalar_one()
    intern_pct = int(round(internships * 100 / sem6_total)) if sem6_total else 0

    # Upcoming events visible to the college
    events = db.execute(
        select(Event).where(Event.college_id == college_id, Event.starts_at >= datetime.datetime.combine(today, datetime.time.min) - datetime.timedelta(days=30),
                            Event.audience.in_(["all", "college", "parents", "students"]), Event.student_id.is_(None))
        .order_by(Event.starts_at).limit(6)
    ).scalars().all()

    reports = db.execute(
        select(ReportRun).where(ReportRun.college_id == college_id, ReportRun.status == "ready").order_by(ReportRun.generated_at.desc()).limit(6)
    ).scalars().all()

    semesters = db.execute(select(func.distinct(Student.semester)).where(Student.college_id == college_id).order_by(Student.semester)).scalars().all()

    return {
        "college": {"name": "Demo Engineering College", "title": "Program Overview"},
        "filters": {"semester": semester, "semesters": list(semesters)},
        "kpis": {
            "students_enrolled": {"value": total, "semesters": f"Sem {sem_min} to {sem_max}" if sem_min else "", "branches": branch_count},
            "avg_attendance": {"value": avg_att, "target": 85, "above_target": avg_att >= 85},
            "certifications": {"value": len(certs), "this_semester": certs_this_sem},
            "internships": {"value": internships, "sem6_pct": intern_pct, "sem6_total": sem6_total},
        },
        "readiness_distribution": distribution,
        "readiness_total": total,
        "branch_readiness": branches,
        "cumulative_certifications": cumulative,
        "upcoming_events": [
            {"id": e.id, "title": e.title_ta if lang == "ta" and e.title_ta else e.title_en, "kind": e.kind,
             "date": e.starts_at.strftime("%b %d"), "starts_at": e.starts_at.isoformat(), "audience": e.audience, "rsvp_enabled": e.rsvp_enabled}
            for e in events
        ],
        "mou_reports": [
            {"id": r.id, "title": r.title_ta if lang == "ta" and r.title_ta else r.title_en, "type": r.report_type, "period": r.period_label,
             "generated_at": r.generated_at.isoformat() if r.generated_at else None, "data_as_of": r.data_as_of.isoformat() if r.data_as_of else None,
             "size_kb": r.file_size_kb, "download_url": f"/api/v1/college/reports/{r.id}/download"}
            for r in reports
        ],
        "thresholds": {"ready_min": cfg.band_ready_min, "nearly_min": cfg.band_nearly_min},
    }
