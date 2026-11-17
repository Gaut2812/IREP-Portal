"""Screen 29 lab orchestrator.

Launch checks, in order: semester entitlement, track entitlement, trainer
approval (Cyber Range), one running lab per student, monthly quota. A
running session has a hard expiry (lab.session_minutes) and an idle limit;
`cull` stops anything past either and writes the minutes to usage_ledger.

LAB_ADAPTER=fake (default) records a workspace without starting anything.
LAB_ADAPTER=docker runs one container per session with no network (or the
isolated cyber-range network), CPU/memory caps and --rm.
"""
import datetime
import shutil
import subprocess
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import VirtualLabItem, LabSession, LabApproval, UsageLedger, Student

MONTHLY_LAB_MINUTES = 1200      # 20 hours of container time per student per month
MONTHLY_CLOUD_CREDITS = 100.0   # education-tier credits per student per month
IDLE_LIMIT_MIN = 30
CLOUD_CREDITS_PER_HOUR = 4.0


class LabLaunchError(Exception):
    def __init__(self, reason: str, message: str, status: int = 403):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.status = status


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

class LabAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def start(self, session: LabSession, lab: VirtualLabItem) -> str:
        """Start the workspace and return a container reference."""

    @abstractmethod
    def stop(self, container_ref: Optional[str]) -> None:
        ...


class FakeLabAdapter(LabAdapter):
    name = "fake"

    def start(self, session, lab):
        return f"fake-{session.id}"

    def stop(self, container_ref):
        return None


class DockerLabAdapter(LabAdapter):
    name = "docker"

    def start(self, session, lab):
        network = "irep-cyber-range" if lab.network == "isolated" else "none"
        cmd = ["docker", "run", "-d", "--rm", "--name", f"irep-lab-{session.id}", "--network", network,
               "--memory", "1g", "--cpus", "1", "--pids-limit", "256", lab.image or "ubuntu:24.04", "sleep", "infinity"]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=True)
        return out.stdout.strip()[:64]

    def stop(self, container_ref):
        if container_ref:
            subprocess.run(["docker", "stop", container_ref], capture_output=True, timeout=60)


def get_lab_adapter() -> LabAdapter:
    if (settings.LAB_ADAPTER or "fake").lower() == "docker" and shutil.which("docker"):
        return DockerLabAdapter()
    return FakeLabAdapter()


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------

def period_of(when: datetime.datetime) -> str:
    return when.strftime("%Y-%m")


def usage(db: Session, student: Student, kind: str, period: str) -> float:
    return float(db.execute(
        select(func.coalesce(func.sum(UsageLedger.amount), 0)).where(
            UsageLedger.student_id == student.id, UsageLedger.kind == kind, UsageLedger.period == period)
    ).scalar_one())


def quota_for(kind: str) -> float:
    return MONTHLY_CLOUD_CREDITS if kind == "cloud_credits" else float(MONTHLY_LAB_MINUTES)


def running_minutes(s: LabSession, now: datetime.datetime) -> int:
    end = s.stopped_at or min(now, s.expires_at)
    return max(0, int((end - s.started_at).total_seconds() // 60))


def _record_usage(db: Session, s: LabSession, lab: VirtualLabItem, minutes: int) -> None:
    amount = round(minutes / 60.0 * CLOUD_CREDITS_PER_HOUR, 2) if lab.meter == "cloud_credits" else float(minutes)
    db.add(UsageLedger(id=f"ul_{uuid.uuid4().hex[:18]}", college_id=s.college_id, student_id=s.student_id,
                       kind=lab.meter, amount=amount, period=period_of(s.started_at), ref_type="lab_session", ref_id=s.id))


def stop_session(db: Session, s: LabSession, reason: str, now: datetime.datetime) -> int:
    if s.status not in ("running", "starting"):
        return 0
    lab = db.execute(select(VirtualLabItem).filter_by(id=s.lab_id)).scalar_one()
    s.stopped_at = min(now, s.expires_at) if reason in ("expired",) else now
    if reason == "idle":
        s.stopped_at = min(now, s.last_active_at + datetime.timedelta(minutes=IDLE_LIMIT_MIN))
    s.status = "expired" if reason in ("expired", "idle") else "stopped"
    s.stop_reason = reason
    minutes = running_minutes(s, now)
    _record_usage(db, s, lab, minutes)
    get_lab_adapter().stop(s.container_ref)
    return minutes


def cull(db: Session, college_id: str, now: Optional[datetime.datetime] = None) -> int:
    """Idle culler / expiry job: stop sessions past their expiry or idle limit."""
    now = now or datetime.datetime.now()
    stopped = 0
    for s in db.execute(select(LabSession).where(LabSession.college_id == college_id, LabSession.status == "running")).scalars().all():
        if now >= s.expires_at:
            stop_session(db, s, "expired", now)
            stopped += 1
        elif now - s.last_active_at >= datetime.timedelta(minutes=IDLE_LIMIT_MIN):
            stop_session(db, s, "idle", now)
            stopped += 1
    return stopped


# ---------------------------------------------------------------------------
# Entitlement
# ---------------------------------------------------------------------------

def approval_for(db: Session, student: Student, lab: VirtualLabItem) -> Optional[LabApproval]:
    return db.execute(
        select(LabApproval).filter_by(student_id=student.id, lab_id=lab.id).order_by(LabApproval.created_at.desc())
    ).scalars().first()


def lock_reason(db: Session, student: Student, lab: VirtualLabItem, now: datetime.datetime) -> Optional[Tuple[str, str]]:
    """Return (reason, message) when the student cannot launch this lab, else None."""
    if student.semester < lab.min_semester:
        return "semester", f"Unlocks in Semester {lab.min_semester}. You are in Semester {student.semester}."
    if lab.allowed_tracks and student.track not in lab.allowed_tracks:
        return "track", f"Available to the {', '.join(lab.allowed_tracks)} track."
    if lab.requires_approval:
        ap = approval_for(db, student, lab)
        if not ap or ap.status != "approved":
            if ap and ap.status == "pending":
                return "approval_pending", "Waiting for your trainer to approve access."
            if ap and ap.status == "denied":
                return "approval_denied", f"Access was declined{': ' + ap.reason if ap.reason else ''}. Talk to your trainer."
            return "approval", "Trainer approval needed. Request access to continue."
    used = usage(db, student, lab.meter, period_of(now))
    if used >= quota_for(lab.meter):
        unit = "cloud credits" if lab.meter == "cloud_credits" else f"{MONTHLY_LAB_MINUTES} lab minutes"
        return "quota", f"You have used all your {unit} for this month. The quota resets on the 1st."
    return None


def launch(db: Session, student: Student, lab: VirtualLabItem, now: Optional[datetime.datetime] = None) -> LabSession:
    now = now or datetime.datetime.now()
    cull(db, student.college_id, now)
    locked = lock_reason(db, student, lab, now)
    if locked:
        raise LabLaunchError(locked[0], locked[1])
    running = db.execute(select(LabSession).filter_by(student_id=student.id, status="running")).scalars().first()
    if running:
        raise LabLaunchError("already_running", "Stop your running lab before launching another one.", status=409)
    adapter = get_lab_adapter()
    # never let one session overrun the remaining monthly quota
    remaining = quota_for(lab.meter) - usage(db, student, lab.meter, period_of(now))
    max_minutes = lab.session_minutes
    if lab.meter == "lab_minutes":
        max_minutes = int(min(max_minutes, remaining))
    s = LabSession(id=f"ls_{uuid.uuid4().hex[:16]}", college_id=student.college_id, lab_id=lab.id, student_id=student.id,
                   status="starting", provider=adapter.name, workspace_file=lab.default_file, started_at=now,
                   expires_at=now + datetime.timedelta(minutes=max(1, max_minutes)), last_active_at=now)
    db.add(s)
    db.flush()
    s.container_ref = adapter.start(s, lab)
    s.status = "running"
    return s
