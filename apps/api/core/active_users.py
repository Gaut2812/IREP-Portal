"""Is this account still active? Checked on every authenticated request and WebSocket, so a
deactivation takes effect at once instead of when the token expires.

- With USER_STATE_CACHE_URL (production: Valkey, see infra/prod/docker-compose.yml) the answer is
  cached for CACHE_SECONDS and the cache entry is deleted the moment a change commits.
- Without it (development, tests) the database is asked every time: always correct, just slower.
- If Valkey is unreachable the database is asked: never fail open.

Invalidation is automatic: any committed change to users.is_active (college settings, staff
accounts, deletion requests, scripts) or a deleted user row clears that user's cache entry.
"""
import logging
from typing import Iterable, Optional

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from core.config import settings

log = logging.getLogger("irep.active_users")
CACHE_SECONDS = 300
_client = None
_client_url: Optional[str] = None


def _key(user_id: str) -> str:
    return f"irep:user_active:{user_id}"


def _cache():
    """A Redis-protocol client for USER_STATE_CACHE_URL, or None."""
    global _client, _client_url
    url = settings.USER_STATE_CACHE_URL
    if not url:
        return None
    if _client is None or _client_url != url:
        import redis
        _client, _client_url = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5), url
    return _client


def _from_db(user_id: str) -> bool:
    from core.database import SessionLocal
    from models.schema import User
    db = SessionLocal()
    try:
        return bool(db.execute(select(User.is_active).where(User.id == user_id)).scalar_one_or_none())
    finally:
        db.close()


def is_active(user_id: Optional[str]) -> bool:
    """False for a deactivated or deleted account (a missing row is not active)."""
    if not user_id:
        return False
    cache = _cache()
    if cache is not None:
        try:
            hit = cache.get(_key(user_id))
            if hit is not None:
                return hit == b"1"
        except Exception as e:                      # Valkey down: ask the database
            log.warning("user state cache unavailable: %s", e.__class__.__name__)
            cache = None
    active = _from_db(user_id)
    if cache is not None:
        try:
            cache.setex(_key(user_id), CACHE_SECONDS, b"1" if active else b"0")
        except Exception:
            pass
    return active


def invalidate(user_ids: Iterable[str]) -> None:
    ids = [i for i in set(user_ids) if i]
    cache = _cache()
    if not ids or cache is None:
        return
    try:
        cache.delete(*[_key(i) for i in ids])
    except Exception as e:
        # the entry expires within CACHE_SECONDS; deactivation also revokes Keycloak sessions
        log.error("could not clear user state cache for %d user(s): %s", len(ids), e.__class__.__name__)


# ---- automatic invalidation on commit ----
_PENDING = "irep_active_changed"


def _register() -> None:
    from models.schema import User

    @event.listens_for(User.is_active, "set")
    def _changed(target, value, oldvalue, initiator):          # noqa: ANN001
        if value != oldvalue and target.id:
            from sqlalchemy.orm import object_session
            s = object_session(target)
            if s is not None:
                s.info.setdefault(_PENDING, set()).add(target.id)

    @event.listens_for(Session, "before_flush")
    def _deleted(session, flush_context, instances):            # noqa: ANN001
        for obj in session.deleted:
            if isinstance(obj, User):
                session.info.setdefault(_PENDING, set()).add(obj.id)

    @event.listens_for(Session, "after_commit")
    def _commit(session):                                         # noqa: ANN001
        ids = session.info.pop(_PENDING, None)
        if ids:
            invalidate(ids)

    @event.listens_for(Session, "after_rollback")
    def _rollback(session):                                       # noqa: ANN001
        session.info.pop(_PENDING, None)


_register()
