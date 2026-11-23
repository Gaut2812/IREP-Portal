"""College / placement-cell screens."""
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, require_role, TokenPayload
from models.schema import ReportRun
from services.college_overview import build_college_overview
from services.reports import ensure_report_file
from services.storage import get_storage
from services.audit import record_audit

router = APIRouter(prefix="/college", tags=["College Screens"])

COLLEGE_ROLES = ["college_admin", "placement_officer", "irep_admin"]


class GenerateReportRequest(BaseModel):
    report_type: str = "progress"   # progress | performance | readiness
    period_label: Optional[str] = None


# --- SCREEN 19: College / Placement Cell Dashboard (PDF 9) ---
@router.get("/overview")
def get_college_overview(
    semester: Optional[int] = None,
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(COLLEGE_ROLES)),
    db: Session = Depends(get_db),
):
    if semester is not None and not (2 <= semester <= 8):
        raise HTTPException(status_code=422, detail="semester must be between 2 and 8")
    return build_college_overview(db, current_user.college_id, semester, lang)


@router.get("/dashboard", include_in_schema=False)
def get_college_dashboard_legacy(
    current_user: TokenPayload = Depends(require_role(COLLEGE_ROLES)),
    db: Session = Depends(get_db),
):
    """Backward-compatible alias for the first-generation endpoint."""
    return build_college_overview(db, current_user.college_id, None, "en")


@router.get("/reports")
def list_reports(
    lang: str = "en",
    current_user: TokenPayload = Depends(require_role(COLLEGE_ROLES)),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(ReportRun).filter_by(college_id=current_user.college_id).order_by(ReportRun.generated_at.desc())
    ).scalars().all()
    return {"reports": [
        {"id": r.id, "title": r.title_ta if lang == "ta" and r.title_ta else r.title_en, "type": r.report_type, "period": r.period_label,
         "generated_at": r.generated_at.isoformat() if r.generated_at else None, "data_as_of": r.data_as_of.isoformat() if r.data_as_of else None,
         "size_kb": r.file_size_kb, "status": r.status, "download_url": f"/api/v1/college/reports/{r.id}/download"}
        for r in rows
    ]}


@router.post("/reports/generate")
def generate_report(
    req: GenerateReportRequest,
    current_user: TokenPayload = Depends(require_role(COLLEGE_ROLES)),
    db: Session = Depends(get_db),
):
    titles = {
        "progress": ("Monthly progress report", "மாதாந்திர முன்னேற்ற அறிக்கை"),
        "performance": ("Semester performance report", "பருவ செயல்திறன் அறிக்கை"),
        "readiness": ("Placement readiness analysis", "வேலைவாய்ப்பு தயார்நிலை பகுப்பாய்வு"),
    }
    if req.report_type not in titles:
        raise HTTPException(status_code=422, detail="Unknown report type")
    overview = build_college_overview(db, current_user.college_id, None, "en")
    now = datetime.datetime.utcnow()
    rid = f"rep_{uuid.uuid4().hex[:12]}"
    en, ta = titles[req.report_type]
    period = req.period_label or now.strftime("%B %Y")
    lines = [
        f"Students enrolled: {overview['kpis']['students_enrolled']['value']}",
        f"Average attendance: {overview['kpis']['avg_attendance']['value']}%",
        f"Certifications earned: {overview['kpis']['certifications']['value']}",
        f"Internships secured: {overview['kpis']['internships']['value']}",
    ] + [f"{b['band']}: {b['percentage']}%" for b in overview["readiness_distribution"]]
    from models.schema import MouTerm   # Screen 20: MoU terms in the report (usage figures follow with 47, L23)
    mou = db.execute(select(MouTerm).where(MouTerm.college_id == current_user.college_id, MouTerm.status == "active")).scalars().first()
    if mou:
        enrolled = overview["kpis"]["students_enrolled"]["value"]
        lines += ["", f"MoU: {mou.starts_on.isoformat()} to {mou.ends_on.isoformat()}",
                  f"Students enrolled against the cap: {enrolled} of {mou.students_cap}",
                  f"Lab hours per student: {mou.lab_hours_per_student} · AI calls per day: {mou.ai_calls_per_day}"]
    from services.quotas import college_usage            # L23: usage figures from 47, this month
    u = college_usage(db, current_user.college_id)
    lines += ["", f"Usage this month ({u['period']}):"] + [
        f"{label}: {u['usage'][k]['used']} of {u['usage'][k]['quota']}" + (f" ({u['usage'][k]['pct']}%)" if u['usage'][k]['pct'] is not None else "")
        for k, label in (("lab_minutes", "Lab minutes"), ("ai_calls", "AI Study Buddy calls"), ("recording_mb", "Recording storage MB"))]
    rel, size_kb = ensure_report_file(rid, f"{en} - {period}", now, now.date(), lines)
    run = ReportRun(id=rid, college_id=current_user.college_id, title_en=f"{en} · {period}", title_ta=f"{ta} · {period}",
                    report_type=req.report_type, period_label=period, generated_at=now, data_as_of=now.date(),
                    file_path=rel, file_size_kb=size_kb, status="ready", generated_by=current_user.sub)
    db.add(run)
    record_audit(db, current_user, "report.generate", "report_run", rid, {"type": req.report_type})
    db.commit()
    return {"success": True, "report": {"id": rid, "title": run.title_en, "download_url": f"/api/v1/college/reports/{rid}/download"}}


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    current_user: TokenPayload = Depends(require_role(COLLEGE_ROLES)),
    db: Session = Depends(get_db),
):
    run = db.execute(select(ReportRun).filter_by(id=report_id, college_id=current_user.college_id)).scalar_one_or_none()
    if not run or not run.file_path:
        raise HTTPException(status_code=404, detail="Report not found")
    storage = get_storage()
    if not storage.exists(run.file_path):
        raise HTTPException(status_code=404, detail="Report file missing")
    record_audit(db, current_user, "report.download", "report_run", run.id)
    db.commit()
    return Response(content=storage.get(run.file_path), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{run.id}.pdf"'})
