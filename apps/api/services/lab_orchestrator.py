"""Labs service (screen 29 and the labs track, Master Plan: "one launcher (JupyterHub)
behind one FastAPI labs service").

Every lab, browser or server, goes through the same checks, in order: semester
entitlement, track entitlement, trainer approval (Cyber Range, with the AUP), one
running lab per student, monthly quota. A running session has a hard expiry
(lab.session_minutes) and an idle limit; `cull` stops anything past either and
writes the minutes to usage_ledger, so the credits meter (47) works for every kind.

Runtimes (virtual_labs.runtime):
- server:   a JupyterHub named server with the lab's profile (LAB_ADAPTER=jupyterhub),
            or a hardened local container (LAB_ADAPTER=docker, development only).
            Starting and stopping are outbox events (`lab.start`, `lab.stop`), never
            calls inside the request transaction (architecture rule 3).
- browser:  runs in the student's browser (PGlite for SQL, Pyodide for Python); the
            page sends signed heartbeat beacons that keep the session alive and meter it.
- external: a sandbox the college already has (AWS Academy Learner Lab); the portal
            records the session and its credits.

LAB_ADAPTER=fake (default) records server workspaces without starting anything;
production refuses it (main.py).
"""
import datetime
import hashlib
import shutil
import subprocess
import uuid
from abc import ABC, abstractmethod
from typing import Optional, Tuple

import httpx
from jose import JWTError, jwt
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import LabApproval, LabSession, OutboxEvent, Student, UsageLedger, VirtualLabItem
from services.outbox import emit, handler

MONTHLY_LAB_MINUTES = 1200      # 20 hours of lab time per student per month
MONTHLY_CLOUD_CREDITS = 100.0   # education-tier credits per student per month
IDLE_LIMIT_MIN = 30
START_TIMEOUT_MIN = 10          # a server that never came up is marked failed
CLOUD_CREDITS_PER_HOUR = 4.0
BEACON_MIN_GAP_SEC = 20


class LabLaunchError(Exception):
    def __init__(self, reason: str, message: str, status: int = 403):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.status = status


# ---------------------------------------------------------------------------
# Adapters (server runtime)
# ---------------------------------------------------------------------------

class LabAdapter(ABC):
    name = "abstract"
    synchronous = False        # True only for adapters that call nothing external

    @abstractmethod
    def start(self, session: LabSession, lab: VirtualLabItem) -> str:
        """Start the workspace and return a reference."""

    @abstractmethod
    def stop(self, ref: Optional[str]) -> None:
        """Stop it. Must be idempotent (outbox handlers can re-run)."""

    def connect_url(self, session: LabSession, lab: VirtualLabItem) -> Optional[str]:
        """A short-lived URL the student opens; None when there is nothing to open."""
        return None


class FakeLabAdapter(LabAdapter):
    name = "fake"
    synchronous = True

    def start(self, session, lab):
        return f"fake-{session.id}"

    def stop(self, ref):
        return None


def docker_run_args(session: LabSession, lab: VirtualLabItem) -> list:
    """Hardened `docker run` for development (the same limits JupyterHub applies in infra/labs)."""
    network = "irep-cyber-range" if lab.network == "isolated" else "none"     # no route to the portal, metadata or the internet
    return ["docker", "run", "-d", "--rm", "--name", f"irep-lab-{session.id}", "--network", network,
            "--memory", "1g", "--memory-swap", "1g", "--cpus", "1", "--pids-limit", "256",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "1000:1000",
            "--read-only", "--tmpfs", "/tmp:rw,size=256m", "--tmpfs", "/home/irep:rw,size=512m,uid=1000",
            "--label", f"irep.session={session.id}", "--label", f"irep.college={session.college_id}",
            lab.image or "ubuntu:24.04", "sleep", str(max(60, lab.session_minutes * 60))]


class DockerLabAdapter(LabAdapter):
    name = "docker"

    def start(self, session, lab):
        out = subprocess.run(docker_run_args(session, lab), capture_output=True, text=True, timeout=60, check=True)
        return out.stdout.strip()[:64]

    def stop(self, ref):
        if ref:
            subprocess.run(["docker", "rm", "-f", ref], capture_output=True, timeout=60)


def hub_username(college_id: str, student_id: str) -> str:
    """No names or emails reach JupyterHub: a stable pseudonym per student."""
    return "s" + hashlib.sha256(f"{college_id}:{student_id}".encode()).hexdigest()[:16]


def hub_server_name(session_id: str) -> str:
    return session_id.replace("_", "-").lower()


class JupyterHubAdapter(LabAdapter):
    """JupyterHub REST API with a service token (infra/labs/jupyterhub_config.py grants it
    only admin:users, admin:servers and tokens). One named server per lab session; the
    profile picks the image and limits on the hub side."""
    name = "jupyterhub"

    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, public_url: Optional[str] = None,
                 client: Optional[httpx.Client] = None):
        self.base = (base_url or settings.JUPYTERHUB_URL).rstrip("/")
        self.public = (public_url or settings.JUPYTERHUB_PUBLIC_URL or self.base).rstrip("/")
        self.token = token if token is not None else settings.JUPYTERHUB_API_TOKEN
        self.client = client or httpx.Client(timeout=30)

    def _h(self):
        return {"Authorization": f"token {self.token}"}

    def _who(self, session: LabSession) -> Tuple[str, str]:
        return hub_username(session.college_id, session.student_id), hub_server_name(session.id)

    def start(self, session, lab):
        user, server = self._who(session)
        r = self.client.post(f"{self.base}/hub/api/users/{user}", headers=self._h())
        if r.status_code not in (201, 409):
            r.raise_for_status()
        r = self.client.post(f"{self.base}/hub/api/users/{user}/servers/{server}", headers=self._h(),
                             json={"profile": lab.profile or "linux", "session": session.id})
        if r.status_code not in (201, 202, 400) or (r.status_code == 400 and "already" not in r.text.lower()):
            r.raise_for_status()
        return f"{user}/{server}"

    def stop(self, ref):
        if not ref or "/" not in ref:
            return
        user, server = ref.split("/", 1)
        r = self.client.request("DELETE", f"{self.base}/hub/api/users/{user}/servers/{server}", headers=self._h(), json={"remove": True})
        if r.status_code not in (202, 204, 404):
            r.raise_for_status()

    def connect_url(self, session, lab):
        if not session.container_ref or "/" not in session.container_ref:
            return None
        user, server = session.container_ref.split("/", 1)
        ttl = max(60, int((session.expires_at - datetime.datetime.now()).total_seconds()))
        r = self.client.post(f"{self.base}/hub/api/users/{user}/tokens", headers=self._h(),
                             json={"expires_in": ttl, "note": f"irep lab {session.id}", "scopes": [f"access:servers!server={user}/{server}"]})
        r.raise_for_status()
        return f"{self.public}/user/{user}/{server}/?token={r.json()['token']}"


def get_lab_adapter() -> LabAdapter:
    kind = (settings.LAB_ADAPTER or "fake").lower()
    if kind == "jupyterhub":
        return JupyterHubAdapter()
    if kind == "docker" and shutil.which("docker"):
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
    if s.provider in ("browser", "external"):
        return minutes                                   # nothing runs on our side
    adapter = get_lab_adapter()
    if adapter.synchronous or s.provider == "fake":
        adapter.stop(s.container_ref)
    else:
        emit(db, "lab.stop", {"session_id": s.id, "ref": s.container_ref}, college_id=s.college_id,
             entity_type="lab_session", entity_id=s.id)
    return minutes


def cull(db: Session, college_id: str, now: Optional[datetime.datetime] = None) -> int:
    """Idle culler / expiry job: stop sessions past their expiry or idle limit, and
    servers that never came up."""
    now = now or datetime.datetime.now()
    stopped = 0
    for s in db.execute(select(LabSession).where(LabSession.college_id == college_id,
                                                 LabSession.status.in_(["running", "starting"]))).scalars().all():
        if s.status == "starting" and now - s.started_at >= datetime.timedelta(minutes=START_TIMEOUT_MIN):
            stop_session(db, s, "start_failed", now)
            s.status = "failed"
            stopped += 1
        elif now >= s.expires_at:
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
    running = db.execute(select(LabSession).where(LabSession.student_id == student.id,
                                                  LabSession.status.in_(["running", "starting"]))).scalars().first()
    if running:
        raise LabLaunchError("already_running", "Stop your running lab before launching another one.", status=409)
    runtime = lab.runtime or "server"
    adapter = get_lab_adapter() if runtime == "server" else None
    provider = adapter.name if adapter else runtime
    # never let one session overrun the remaining monthly quota
    remaining = quota_for(lab.meter) - usage(db, student, lab.meter, period_of(now))
    max_minutes = lab.session_minutes
    if lab.meter == "lab_minutes":
        max_minutes = int(min(max_minutes, remaining))
    s = LabSession(id=f"ls_{uuid.uuid4().hex[:16]}", college_id=student.college_id, lab_id=lab.id, student_id=student.id,
                   status="starting", provider=provider, workspace_file=lab.default_file, started_at=now,
                   expires_at=now + datetime.timedelta(minutes=max(1, max_minutes)), last_active_at=now)
    db.add(s)
    db.flush()
    if adapter is None:                                   # browser or external: nothing to start on our side
        s.container_ref, s.status = f"{provider}-{s.id}", "running"
    elif adapter.synchronous:
        s.container_ref, s.status = adapter.start(s, lab), "running"
    else:                                                 # JupyterHub / Docker: after commit, through the outbox
        emit(db, "lab.start", {"session_id": s.id}, college_id=s.college_id, entity_type="lab_session", entity_id=s.id)
    return s


@handler("lab.start")
def _start_server(db: Session, ev: OutboxEvent) -> None:
    """Idempotent: a session that is no longer starting (stopped, culled, already up) is left alone."""
    s = db.get(LabSession, (ev.payload or {}).get("session_id"))
    if s is None or s.status != "starting":
        return
    lab = db.get(VirtualLabItem, s.lab_id)
    adapter = get_lab_adapter()
    try:
        s.container_ref = adapter.start(s, lab)
    except Exception:
        if ev.attempts + 1 >= settings.OUTBOX_MAX_ATTEMPTS:
            s.status, s.stop_reason, s.stopped_at = "failed", "start_failed", datetime.datetime.now()
            return
        raise
    s.status = "running"
    s.last_active_at = datetime.datetime.now()


@handler("lab.stop")
def _stop_server(db: Session, ev: OutboxEvent) -> None:
    get_lab_adapter().stop((ev.payload or {}).get("ref"))


def connect_url(db: Session, s: LabSession, lab: VirtualLabItem) -> Optional[str]:
    if s.status != "running":
        return None
    if (lab.runtime or "server") == "external":
        return lab.external_url
    if (lab.runtime or "server") == "server":
        return get_lab_adapter().connect_url(s, lab)
    return None


# ---------------------------------------------------------------------------
# Browser labs: signed beacons (tokens scoped to one session)
# ---------------------------------------------------------------------------

def _beacon_key() -> str:
    return settings.JWT_SECRET_KEY + ":lab-beacon"      # never valid as an access token


def beacon_token(s: LabSession) -> str:
    return jwt.encode({"sid": s.id, "std": s.student_id, "col": s.college_id, "typ": "lab_beacon",
                       "exp": int(s.expires_at.timestamp()) + 300}, _beacon_key(), algorithm="HS256")


def accept_beacon(db: Session, token: str, now: Optional[datetime.datetime] = None) -> Optional[LabSession]:
    """Refresh last_active_at for the session the token names. None when invalid or not running."""
    try:
        claims = jwt.decode(token, _beacon_key(), algorithms=["HS256"])
    except JWTError:
        return None
    if claims.get("typ") != "lab_beacon":
        return None
    s = db.execute(select(LabSession).where(LabSession.id == claims.get("sid"), LabSession.student_id == claims.get("std"),
                                            LabSession.college_id == claims.get("col"))).scalar_one_or_none()
    if s is None or s.status != "running":
        return s
    now = now or datetime.datetime.now()
    if (now - s.last_active_at).total_seconds() >= BEACON_MIN_GAP_SEC:
        s.last_active_at = now
    return s
