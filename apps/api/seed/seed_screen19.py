"""Screen 19 seed: three MoU report runs with downloadable PDF files."""
import datetime

from sqlalchemy import select

from models.schema import ReportRun
from services.reports import ensure_report_file

REPORTS = [
    ("rep_sep_progress", "September progress report", "செப்டம்பர் முன்னேற்ற அறிக்கை", "progress", "September 2026",
     datetime.datetime(2026, 10, 2, 9, 30), datetime.date(2026, 9, 30),
     ["Students enrolled: 612 across 4 branches", "Average attendance: 89%", "Certifications earned to date: 143"]),
    ("rep_sem4_performance", "Sem 4 performance report", "பருவம் 4 செயல்திறன் அறிக்கை", "performance", "Semester 4",
     datetime.datetime(2026, 10, 20, 11, 0), datetime.date(2026, 10, 18),
     ["Semester 4 cohort: 85 students", "Average readiness: 73", "Practice tests completed: 1,240"]),
    ("rep_readiness_analysis", "Placement readiness analysis", "வேலைவாய்ப்பு தயார்நிலை பகுப்பாய்வு", "readiness", "All semesters",
     datetime.datetime(2026, 11, 3, 8, 15), datetime.date(2026, 11, 1),
     ["Placement Ready: 55%", "Nearly Ready: 29%", "Needs Support: 16%", "Branch leaders: CSE (78), AI & DS (77)"]),
]


def seed_screen19(db, college_id: str = "col_demo_001") -> int:
    created = 0
    for rid, en, ta, rtype, period, generated, as_of, lines in REPORTS:
        if db.execute(select(ReportRun).filter_by(id=rid)).first():
            continue
        rel, size_kb = ensure_report_file(rid, en, generated, as_of, lines)
        db.add(ReportRun(id=rid, college_id=college_id, title_en=en, title_ta=ta, report_type=rtype, period_label=period,
                         generated_at=generated, data_as_of=as_of, file_path=rel, file_size_kb=size_kb, status="ready",
                         generated_by="system"))
        created += 1
    db.flush()
    return created
