"""Server-lab metering (labs track S13): "usage is metered by cAdvisor for server labs and by
heartbeat beacons for browser labs" (Master Plan).

Every few minutes `meter()` reads cAdvisor's Docker API on the lab node, matches containers to
lab sessions by their `irep.session` label (set by infra/labs/hub/jupyterhub_config.py and by
the docker dev adapter), and records cumulative CPU seconds and peak memory on the session.
A session that used at least ACTIVE_CPU_SECONDS of CPU since the last sample counts as
active, so a running notebook or build is not culled as idle just because the tab is closed.

LAB_METER_URL empty = metering off (dev); the minutes-based usage ledger works either way.
"""
import datetime
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import LabSession

ACTIVE_CPU_SECONDS = 2.0


class CadvisorClient:
    def __init__(self, base_url: Optional[str] = None, client: Optional[httpx.Client] = None):
        self.base = (base_url or settings.LAB_METER_URL).rstrip("/")
        self.client = client or httpx.Client(timeout=20)

    def containers(self) -> List[Dict]:
        """[{session, cpu_seconds, mem_mb}] for containers labelled irep.session."""
        r = self.client.get(f"{self.base}/api/v1.3/docker")
        r.raise_for_status()
        out = []
        for info in r.json().values():
            labels = (info.get("spec") or {}).get("labels") or {}
            sid = labels.get("irep.session")
            stats = info.get("stats") or []
            if not sid or not stats:
                continue
            last = stats[-1]
            cpu_ns = ((last.get("cpu") or {}).get("usage") or {}).get("total") or 0
            mem = (last.get("memory") or {}).get("usage") or 0
            out.append({"session": sid, "cpu_seconds": cpu_ns / 1e9, "mem_mb": int(mem / (1024 * 1024))})
        return out


def meter(db: Session, client: Optional[CadvisorClient] = None, now: Optional[datetime.datetime] = None) -> dict:
    """Apply one cAdvisor sample. Idempotent; does not commit."""
    if client is None and not settings.LAB_METER_URL:
        return {"skipped": True}
    client = client or CadvisorClient()
    now = now or datetime.datetime.now()
    samples = {c["session"]: c for c in client.containers()}
    if not samples:
        return {"sessions": 0, "active": 0}
    active = 0
    for s in db.execute(select(LabSession).where(LabSession.id.in_(list(samples)), LabSession.status == "running")).scalars():
        c = samples[s.id]
        if c["cpu_seconds"] - (s.cpu_seconds or 0) >= ACTIVE_CPU_SECONDS:
            s.last_active_at = max(s.last_active_at, now)
            active += 1
        s.cpu_seconds = max(s.cpu_seconds or 0, c["cpu_seconds"])
        s.mem_peak_mb = max(s.mem_peak_mb or 0, c["mem_mb"])
        s.metered_at = now
    db.flush()
    return {"sessions": len(samples), "active": active}
