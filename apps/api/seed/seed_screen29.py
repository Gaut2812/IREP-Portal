"""Screen 29 seed: lab entitlements/metering, Priya's demo usage, and the PDF 5
state (AI Notebook running for 38 minutes, Docker used yesterday, cloud credits
at 68%, Cyber Range not yet requested). Runs on every seed and restores that
demo state for Priya only."""
import datetime
import uuid

from sqlalchemy import select, delete

from models.schema import VirtualLabItem, LabSession, LabApproval, UsageLedger

LAB_CONFIG = {
    "lab_linux": dict(min_semester=2, allowed_tracks=None, session_minutes=120, meter="lab_minutes", icon="terminal", image="ubuntu:24.04", network="none", default_file="~/practice.sh"),
    "lab_docker_k8s": dict(min_semester=5, allowed_tracks=None, session_minutes=120, meter="lab_minutes", icon="container", image="irep/docker-k8s:1", network="none", default_file="deploy.yaml"),
    "lab_cloud": dict(min_semester=5, allowed_tracks=None, session_minutes=120, meter="cloud_credits", icon="cloud", image=None, network="none", default_file="main.tf"),
    "lab_ai_notebook": dict(min_semester=2, allowed_tracks=["AI & Data Science"], session_minutes=120, meter="lab_minutes", icon="cpu", image="jupyter/scipy-notebook", network="none", default_file="rag_notes_demo.ipynb"),
    "lab_cyber_range": dict(min_semester=5, allowed_tracks=None, session_minutes=90, meter="lab_minutes", icon="shield", image="irep/cyber-range:1", network="isolated", default_file="targets.txt"),
    "lab_fullstack": dict(min_semester=3, allowed_tracks=None, session_minutes=120, meter="lab_minutes", icon="code", image="irep/fullstack:1", network="none", default_file="server.js"),
}
PRIYA = "std_priya_01"
DEMO_SESSION = "ls_demo_priya_notebook"


def seed_screen29(db, college_id: str = "col_demo_001") -> None:
    for lab_id, cfg in LAB_CONFIG.items():
        lab = db.execute(select(VirtualLabItem).filter_by(id=lab_id)).scalar_one_or_none()
        if lab:
            for k, v in cfg.items():
                setattr(lab, k, v)
            lab.is_active_session = False
    db.flush()

    now = datetime.datetime.now()
    period = now.strftime("%Y-%m")
    # restore Priya's demo state
    db.execute(delete(LabApproval).where(LabApproval.student_id == PRIYA, LabApproval.lab_id == "lab_cyber_range"))
    for s in db.execute(select(LabSession).where(LabSession.student_id == PRIYA, LabSession.status == "running", LabSession.id != DEMO_SESSION)).scalars().all():
        s.status, s.stopped_at, s.stop_reason = "stopped", now, "user"
    # the demo session id is reused on every re-seed: drop the usage it logged in earlier runs
    db.execute(delete(UsageLedger).where(UsageLedger.ref_id == DEMO_SESSION))
    demo = db.execute(select(LabSession).filter_by(id=DEMO_SESSION)).scalar_one_or_none()
    started = now - datetime.timedelta(minutes=38)
    if not demo:
        demo = LabSession(id=DEMO_SESSION, college_id=college_id, lab_id="lab_ai_notebook", student_id=PRIYA, provider="fake",
                          container_ref=f"fake-{DEMO_SESSION}", workspace_file="rag_notes_demo.ipynb",
                          started_at=started, expires_at=started + datetime.timedelta(minutes=120), last_active_at=now)
        db.add(demo)
    demo.status, demo.started_at, demo.expires_at, demo.last_active_at = "running", started, started + datetime.timedelta(minutes=120), now
    demo.stopped_at = demo.stop_reason = None

    # "Last used: yesterday" for Docker, and the month's metered usage
    if not db.execute(select(LabSession).filter_by(id="ls_demo_priya_docker")).first():
        y = now - datetime.timedelta(days=1, hours=2)
        db.add(LabSession(id="ls_demo_priya_docker", college_id=college_id, lab_id="lab_docker_k8s", student_id=PRIYA, provider="fake",
                          status="stopped", workspace_file="deploy.yaml", started_at=y, expires_at=y + datetime.timedelta(minutes=120),
                          last_active_at=y + datetime.timedelta(minutes=55), stopped_at=y + datetime.timedelta(minutes=55), stop_reason="user"))
    db.execute(delete(UsageLedger).where(UsageLedger.student_id == PRIYA, UsageLedger.ref_type == "demo"))
    db.add(UsageLedger(id=f"ul_demo_{uuid.uuid4().hex[:10]}", college_id=college_id, student_id=PRIYA, kind="lab_minutes",
                       amount=640, period=period, ref_type="demo", ref_id="month_to_date"))
    db.add(UsageLedger(id=f"ul_demo_{uuid.uuid4().hex[:10]}", college_id=college_id, student_id=PRIYA, kind="cloud_credits",
                       amount=32, period=period, ref_type="demo", ref_id="month_to_date"))
    db.flush()
