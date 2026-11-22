"""ops/golive_check.py: refuses go-live until the bootstrap admin is gone, secrets are real, there is no
demo data, backups are encrypted and a restore has been recorded."""
import datetime
import json
import os
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import httpx
import pytest

from core.config import settings
from core.database import SessionLocal
from ops import golive_check as gl

NOW = datetime.datetime(2026, 11, 22, 9, 0)
AGE_HEADER = b"age-encryption.org/v1\n-> X25519 abc\n"
GOOD_ENV = {
    "POSTGRES_PASSWORD": "a" * 64, "KC_DB_PASSWORD": "b" * 64, "VALKEY_PASSWORD": "c" * 64, "JWT_SECRET_KEY": "d" * 64,
    "KEYCLOAK_ADMIN_PASSWORD": "e" * 32, "GITHUB_WEBHOOK_SECRET": "f" * 64, "SMTP_USER": "mailer", "SMTP_PASSWORD": "g" * 20,
    "LIVE_CLASS_ADAPTER": "teams", "GRAPH_CLIENT_SECRET": "h" * 30, "SMS_PROVIDER": "off",
    "BACKUP_AGE_RECIPIENT": "age1qyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqszqgpqyqs3290gq",
}


def _prod_settings(**over):
    good = dict(ENVIRONMENT="production", AUTH_PROVIDER="keycloak", JWT_SECRET_KEY="d" * 64,
                PUBLIC_BASE_URL="https://portal.example.in", KEYCLOAK_URL="https://id.example.in",
                DATABASE_URL="postgresql+psycopg2://irep:x@postgres:5432/irep", GITHUB_WEBHOOK_SECRET="f" * 64,
                ALLOW_DEMO_ADAPTERS="judge0,labs,study_buddy", LIVE_CLASS_ADAPTER="teams", GRAPH_TENANT_ID="t",
                GRAPH_CLIENT_ID="c", GRAPH_CLIENT_SECRET="s", NOTIFY_ADAPTER="live", SMTP_HOST="smtp.example.in",
                SMTP_FROM="no-reply@example.in", SMS_PROVIDER="off", PARENT_OTP_CHANNEL="email", STORAGE_ADAPTER="local",
                OUTBOX_RUNNER="celery", AV_ADAPTER="clamd")
    return settings.model_copy(update={**good, **over})


class FakeKC:
    def __init__(self, users):
        self.base = "http://kc"
        self.http = httpx.Client(transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json=users) if req.url.path == "/admin/realms/master/users" else httpx.Response(404)))


class NoDemoDB:
    def execute(self, *_):
        class R:
            def scalars(self):
                return self

            def all(self):
                return []
        return R()


def _backups(tmp_path: Path, *, fresh=True, encrypted=True, drill_days_ago=10):
    root = tmp_path / "backups"
    folder = root / "2026-11-22_0215"
    folder.mkdir(parents=True)
    for name in ("irep.dump.age", "keycloak.dump.age", "uploads.tar.gz.age"):
        (folder / name).write_bytes(AGE_HEADER + os.urandom(64) if encrypted else b"PGDMP plain")
    (folder / "SHA256SUMS").write_text("x")
    (folder / "RECIPIENT").write_text(GOOD_ENV["BACKUP_AGE_RECIPIENT"])
    mtime = (NOW - datetime.timedelta(hours=2 if fresh else 80)).timestamp()
    os.utime(folder, (mtime, mtime))
    if drill_days_ago is not None:
        at = (NOW - datetime.timedelta(days=drill_days_ago)).isoformat()
        (root / "restore-drills.log").write_text(json.dumps({"at": at, "backup": folder.name, "kind": "restore"}) + "\n")
    return root


def test_everything_ready_passes(tmp_path):
    results = gl.run(GOOD_ENV, _backups(tmp_path), now=NOW, admin_factory=lambda: FakeKC([{"username": "ops-admin", "attributes": {}}]),
                     db=NoDemoDB(), settings=_prod_settings())
    assert all(ok for _, ok, _ in results), results


def test_bootstrap_admin_still_present_fails():
    ok, msg = gl.check_keycloak_bootstrap_admin(lambda: FakeKC([{"username": "admin", "attributes": {"is_temporary_admin": ["true"]}}]))
    assert not ok and "bootstrap admin still exists: admin" in msg

    def unreachable():
        raise httpx.ConnectError("refused")
    ok, msg = gl.check_keycloak_bootstrap_admin(unreachable)
    assert not ok and "could not read" in msg                                        # cannot prove it: fail


@pytest.mark.parametrize("key, value, why", [
    ("POSTGRES_PASSWORD", "CHANGE_ME", "placeholder"),
    ("KEYCLOAK_ADMIN_PASSWORD", "admin", "placeholder"),
    ("JWT_SECRET_KEY", "short-secret", "shorter than 32"),
    ("SMTP_PASSWORD", "", "placeholder"),
    ("GRAPH_CLIENT_SECRET", "x", "placeholder"),
])
def test_default_or_weak_secrets_fail(key, value, why):
    ok, msg = gl.check_secrets({**GOOD_ENV, key: value}, _prod_settings())
    assert not ok and key in msg and why in msg


def test_production_problems_are_part_of_the_secrets_check():
    ok, msg = gl.check_secrets(GOOD_ENV, _prod_settings(AV_ADAPTER="fake"))
    assert not ok and "AV_ADAPTER must be clamd" in msg


def test_demo_data_fails_on_a_seeded_database():
    db = SessionLocal()
    try:
        ok, msg = gl.check_demo_data(db)                          # the development database is seeded
    finally:
        db.close()
    assert not ok and "@demo.edu" in msg


def test_backups_must_be_encrypted_and_recent(tmp_path):
    ok, msg = gl.check_backups_encrypted({**GOOD_ENV, "BACKUP_AGE_RECIPIENT": "CHANGE_ME"}, _backups(tmp_path / "a"), NOW)
    assert not ok and "not an age public key" in msg
    ok, msg = gl.check_backups_encrypted(GOOD_ENV, _backups(tmp_path / "b", encrypted=False), NOW)
    assert not ok and "not age-encrypted" in msg
    root = _backups(tmp_path / "c")
    (root / "2026-11-22_0215" / "irep.dump").write_bytes(b"PGDMP plain")       # a stray plain dump
    ok, msg = gl.check_backups_encrypted(GOOD_ENV, root, NOW)
    assert not ok and "unencrypted files" in msg and "irep.dump" in msg
    ok, msg = gl.check_backups_encrypted(GOOD_ENV, _backups(tmp_path / "d", fresh=False), NOW)
    assert not ok and "days old" in msg
    ok, msg = gl.check_backups_encrypted(GOOD_ENV, tmp_path / "missing", NOW)
    assert not ok and "run backup.sh once" in msg


def test_a_restore_must_be_recorded_and_recent(tmp_path):
    ok, msg = gl.check_restore_recorded(_backups(tmp_path / "a", drill_days_ago=None), NOW)
    assert not ok and "no restore drill recorded" in msg
    ok, msg = gl.check_restore_recorded(_backups(tmp_path / "b", drill_days_ago=400), NOW)
    assert not ok and "do one again" in msg
    ok, msg = gl.check_restore_recorded(_backups(tmp_path / "c", drill_days_ago=3), NOW)
    assert ok


def test_cli_exits_1_and_names_every_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gl, "run", lambda env, backups: [("secrets", False, "JWT_SECRET_KEY is a placeholder"), ("demo_data", True, "ok")])
    monkeypatch.setattr(sys, "argv", ["golive_check.py", "--backups", str(tmp_path)])
    assert gl.main() == 1
    out = capsys.readouterr().out
    assert "FAIL  secrets" in out and "PASS  demo_data" in out and "NOT ready for go-live: 1 check(s) failed" in out
