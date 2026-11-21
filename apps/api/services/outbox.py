"""Transactional outbox (Master Plan architecture rule: outbox for every state change).

Write side:  ``emit(db, ...)`` adds an OutboxEvent to the caller's session. It
commits (or rolls back) together with the state change, so a side effect can
never fire for a change that did not happen, and never be lost for one that did.

Read side:   ``dispatch_pending(...)`` runs the registered handler for each due
event in its own transaction. A handler that raises is retried with
exponential backoff; after OUTBOX_MAX_ATTEMPTS the event is parked as
``failed`` for an operator. Events with no handler are marked ``done``
(they are recorded for audit/replay; subscribers can be added later).

Handlers must be idempotent: a crash between the side effect and the commit
re-runs the event.

Who drains it: the API's background thread in development (OUTBOX_RUNNER=thread),
the Celery worker in apps/workers in pilot and production (OUTBOX_RUNNER=celery).
"""
import datetime
import logging
import threading
import uuid
from typing import Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from models.schema import OutboxEvent

log = logging.getLogger("irep.outbox")

Handler = Callable[[Session, OutboxEvent], None]
_HANDLERS: Dict[str, Handler] = {}


def handler(event_type: str):
    """Register the handler for one event type (exact match)."""
    def deco(fn: Handler) -> Handler:
        if event_type in _HANDLERS and _HANDLERS[event_type] is not fn:
            raise ValueError(f"outbox handler for {event_type!r} registered twice")
        _HANDLERS[event_type] = fn
        return fn
    return deco


def emit(
    db: Session,
    event_type: str,
    payload: Optional[dict] = None,
    *,
    college_id: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    delay_seconds: float = 0,
) -> OutboxEvent:
    """Queue an event in the caller's transaction. Does not commit."""
    now = datetime.datetime.utcnow()
    ev = OutboxEvent(
        id=f"obx_{uuid.uuid4().hex[:24]}",
        college_id=college_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        status="pending",
        attempts=0,
        available_at=now + datetime.timedelta(seconds=delay_seconds),
    )
    db.add(ev)
    return ev


def _backoff(attempts: int) -> datetime.timedelta:
    return datetime.timedelta(seconds=min(2 ** attempts * 5, 3600))


def _load_handlers() -> None:
    # import modules that register handlers so a bare worker process sees them
    import services.notifications  # noqa: F401
    import services.teams  # noqa: F401
    import services.at_risk  # noqa: F401  (at_risk.parent_call held over quiet hours)
    import routers.admin_colleges  # noqa: F401  (identity.invite_user)
    import routers.audit_consent  # noqa: F401  (data_request.build_export)


def dispatch_pending(session_factory: Callable[[], Session], limit: int = 100) -> dict:
    """Process up to ``limit`` due events. Returns counts by outcome."""
    _load_handlers()
    counts = {"done": 0, "retry": 0, "failed": 0}
    with session_factory() as db:
        q = (select(OutboxEvent.id)
             .where(OutboxEvent.status == "pending", OutboxEvent.available_at <= datetime.datetime.utcnow())
             .order_by(OutboxEvent.available_at, OutboxEvent.id)
             .limit(limit))
        ids = list(db.execute(q).scalars())

    for event_id in ids:
        with session_factory() as db:
            stmt = select(OutboxEvent).where(OutboxEvent.id == event_id, OutboxEvent.status == "pending")
            if db.get_bind().dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)   # several workers never take the same event
            ev = db.execute(stmt).scalar_one_or_none()
            if ev is None:
                continue
            fn = _HANDLERS.get(ev.event_type)
            try:
                if fn is not None:
                    fn(db, ev)
                ev.status, ev.processed_at, ev.last_error = "done", datetime.datetime.utcnow(), None
                ev.attempts += 1
                db.commit()
                counts["done"] += 1
            except Exception as exc:  # noqa: BLE001 - any handler error is retried
                db.rollback()
                ev = db.get(OutboxEvent, event_id)
                ev.attempts += 1
                ev.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if ev.attempts >= settings.OUTBOX_MAX_ATTEMPTS:
                    ev.status = "failed"
                    counts["failed"] += 1
                    log.error("outbox event %s (%s) failed permanently: %s", ev.id, ev.event_type, ev.last_error)
                else:
                    ev.available_at = datetime.datetime.utcnow() + _backoff(ev.attempts)
                    counts["retry"] += 1
                    log.warning("outbox event %s (%s) will retry: %s", ev.id, ev.event_type, ev.last_error)
                db.commit()
    return counts


# ---- development runner: a daemon thread inside the API process ----
_stop = threading.Event()
_thread: Optional[threading.Thread] = None


def start_background_dispatcher(session_factory: Callable[[], Session]) -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()

    def loop():
        while not _stop.wait(settings.OUTBOX_POLL_SECONDS):
            try:
                dispatch_pending(session_factory)
            except Exception:  # noqa: BLE001 - keep the loop alive; the next tick retries
                log.exception("outbox dispatcher tick failed")

    _thread = threading.Thread(target=loop, name="outbox-dispatcher", daemon=True)
    _thread.start()


def stop_background_dispatcher() -> None:
    _stop.set()
