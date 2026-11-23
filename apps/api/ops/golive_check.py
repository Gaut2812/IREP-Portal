"""Pre-go-live checklist: refuses (exit 1) until the server is safe for real students and parents.

    cd /opt/irep/infra/prod && sudo ./golive-check.sh          # wraps the command below
    docker compose run --rm -v /var/backups/irep:/backups:ro api python ops/golive_check.py --backups /backups

Checks:
1. keycloak_bootstrap_admin  The temporary bootstrap admin (KC_BOOTSTRAP_ADMIN_*) is gone from the
                             master realm (replaced by a named admin with two-factor).
2. secrets                   core/production.problems() is clean, every secret in .env is set, is not
                             a placeholder or a well-known default, and is long enough.
3. demo_data                 No demo accounts (seeded @demo.edu / irep.demo users) in this database.
4. backups_encrypted         BACKUP_AGE_RECIPIENT is an age public key, the latest backup is less than
                             36 hours old, and every backup file is age-encrypted (no plain dumps).
5. restore_recorded          restore.sh has recorded a restore drill in the last 180 days.
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Callable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

Result = Tuple[bool, str]

# name: minimum length (generated with openssl rand -hex 32 in DEPLOY.md)
SECRETS = {"POSTGRES_PASSWORD": 24, "KC_DB_PASSWORD": 24, "VALKEY_PASSWORD": 24, "JWT_SECRET_KEY": 32,
           "KEYCLOAK_ADMIN_PASSWORD": 16, "GITHUB_WEBHOOK_SECRET": 24}
KNOWN_DEFAULTS = {"", "admin", "password", "password123", "changeme", "change_me", "secret", "irep", "postgres",
                  "keycloak", "kcadmin", "test", "x", "dev_github_webhook_secret", "irep_super_secret_jwt_key_2026_antigravity",
                  "bbb_demo_secret_2026"}
DEMO_DOMAINS = ("@demo.edu", "@irep.demo")
MAX_BACKUP_AGE = datetime.timedelta(hours=36)
MAX_DRILL_AGE = datetime.timedelta(days=180)
ALLOWED_IN_BACKUP = {"SHA256SUMS", "RECIPIENT"}


def _weak(value: str, min_len: int) -> Optional[str]:
    v = (value or "").strip()
    if v.lower() in KNOWN_DEFAULTS or "change_me" in v.lower() or "changeme" in v.lower():
        return "is a placeholder or a well-known default"
    if len(v) < min_len:
        return f"is shorter than {min_len} characters"
    return None


def check_secrets(env: dict, settings) -> Result:
    from core.production import problems
    bad = [f"{k} {why}" for k, n in SECRETS.items() if (why := _weak(env.get(k, ""), n))]
    conditional = [("SMTP_PASSWORD", env.get("SMTP_USER")), ("GRAPH_CLIENT_SECRET", env.get("LIVE_CLASS_ADAPTER", "").lower() == "teams"),
                   ("FAST2SMS_API_KEY", env.get("SMS_PROVIDER", "").lower() == "fast2sms"),
                   ("MSG91_AUTH_KEY", env.get("SMS_PROVIDER", "").lower() == "msg91")]
    bad += [f"{k} {why}" for k, needed in conditional if needed and (why := _weak(env.get(k, ""), 8))]
    bad += problems(settings)
    return (not bad, "all secrets set and not defaults" if not bad else "; ".join(bad))


def check_keycloak_bootstrap_admin(admin_factory: Callable) -> Result:
    try:
        kc = admin_factory()
        users = kc.http.get(f"{kc.base}/admin/realms/master/users", params={"briefRepresentation": "false", "max": 200}).raise_for_status().json()
    except Exception as e:                                         # unreachable or wrong credentials: cannot prove it is gone
        return False, f"could not read Keycloak's master realm ({e.__class__.__name__}); check KEYCLOAK_ADMIN_* and run again"
    temp = [u["username"] for u in users if (u.get("attributes") or {}).get("is_temporary_admin") == ["true"]]
    if temp:
        return False, (f"bootstrap admin still exists: {', '.join(temp)}. Create a named admin with two-factor in the master realm, "
                       "point KEYCLOAK_ADMIN_USER/PASSWORD at it (or a service account), then delete the bootstrap user")
    return True, "no temporary bootstrap admin in the master realm"


def check_demo_data(db) -> Result:
    from sqlalchemy import or_, select
    from models.schema import User
    rows = db.execute(select(User.email).where(or_(*[User.email.like(f"%{d}") for d in DEMO_DOMAINS])).limit(5)).scalars().all()
    return (not rows, "no demo accounts" if not rows else f"demo accounts present (e.g. {', '.join(rows)}): this database was seeded; start from an empty one")


def _backup_folders(root: Path) -> List[Path]:
    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)


def check_backups_encrypted(env: dict, root: Path, now: datetime.datetime) -> Result:
    recipient = (env.get("BACKUP_AGE_RECIPIENT") or "").strip()
    if not recipient.startswith("age1"):
        return False, "BACKUP_AGE_RECIPIENT is not an age public key (age1...): backups would not be encrypted"
    if not root.is_dir():
        return False, f"no backup folder at {root}: run backup.sh once"
    plain = [p.relative_to(root).as_posix() for p in root.rglob("*")
             if p.is_file() and p.parent != root and p.suffix != ".age" and p.name not in ALLOWED_IN_BACKUP]
    if plain:
        return False, f"unencrypted files in the backups: {', '.join(plain[:5])} (delete them; backup.sh writes only .age files)"
    not_age = [p.relative_to(root).as_posix() for p in root.rglob("*.age") if not p.read_bytes()[:21].startswith(b"age-encryption.org/v1")]
    if not_age:
        return False, f"files named .age that are not age-encrypted: {', '.join(not_age[:5])}"
    folders = _backup_folders(root)
    if not folders:
        return False, "no backup yet: run backup.sh once and schedule it (DEPLOY.md step 10)"
    latest = folders[-1]
    age = now - datetime.datetime.fromtimestamp(latest.stat().st_mtime)
    if age > MAX_BACKUP_AGE:
        return False, f"the latest backup ({latest.name}) is {age.days} days old: is the nightly cron job running?"
    if not list(latest.glob("*.age")):
        return False, f"the latest backup ({latest.name}) has no encrypted files"
    return True, f"latest backup {latest.name} is encrypted"


def check_restore_recorded(root: Path, now: datetime.datetime) -> Result:
    log = root / "restore-drills.log"
    if not log.is_file():
        return False, "no restore drill recorded: restore a backup with restore.sh (DEPLOY.md, 'Restore from a backup')"
    drills = []
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if row.get("kind") == "restore":
                drills.append(datetime.datetime.fromisoformat(row["at"]).replace(tzinfo=None))
        except (ValueError, KeyError):
            continue
    if not drills:
        return False, "the restore-drill log has no restore in it"
    last = max(drills)
    if now - last > MAX_DRILL_AGE:
        return False, f"the last restore drill was on {last.date()}: do one again (every term)"
    return True, f"restore drill on {last.date()}"


def run(env: dict, backups: Path, now: Optional[datetime.datetime] = None, admin_factory: Optional[Callable] = None,
        db=None, settings=None) -> List[Tuple[str, bool, str]]:
    now = now or datetime.datetime.now()
    if settings is None:
        from core.config import settings
    if admin_factory is None:
        from services.keycloak_admin import admin_from_env as admin_factory
    own_db = db is None
    if own_db:
        from core.database import SessionLocal
        db = SessionLocal()
    try:
        return [
            ("keycloak_bootstrap_admin", *check_keycloak_bootstrap_admin(admin_factory)),
            ("secrets", *check_secrets(env, settings)),
            ("demo_data", *check_demo_data(db)),
            ("backups_encrypted", *check_backups_encrypted(env, backups, now)),
            ("restore_recorded", *check_restore_recorded(backups, now)),
        ]
    finally:
        if own_db:
            db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backups", default="/backups", help="the backup folder, mounted read-only")
    args = ap.parse_args()
    results = run(dict(os.environ), Path(args.backups))
    for name, ok, msg in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<26} {msg}")
    failed = [n for n, ok, _ in results if not ok]
    print("\nReady for go-live." if not failed else f"\nNOT ready for go-live: {len(failed)} check(s) failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
