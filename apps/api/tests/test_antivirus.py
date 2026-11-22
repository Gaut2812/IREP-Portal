"""Every upload is virus-scanned before it is saved (services/antivirus.py). Infected files are
quarantined, audited and refused in English and Tamil; when the scanner is down nothing is saved."""
import datetime
import os
import socket
import sys
import threading
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.config import settings
from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import AuditLog, Certificate, Interview
from services import antivirus
from services.antivirus import EICAR, ClamdScanner, ScannerUnavailable
from services.live_sessions import sign_url
from services.storage import get_storage

client = TestClient(app)
REPO = Path(__file__).resolve().parents[3]
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _h(sub, role):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": "col_demo_001"})}


PRIYA, ARUN, KAVITHA = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_kavitha_01", "college_admin")


def _external(data: bytes, title: str):
    return client.post("/api/v1/student/certificates", headers=PRIYA, files={"file": ("proof.png", data, "image/png")},
                       data={"title": title, "issuer": "AWS", "issued_on": datetime.date.today().isoformat()})


def _cleanup(title):
    db = SessionLocal()
    try:
        for c in db.execute(select(Certificate).where(Certificate.title == title)).scalars():
            db.delete(c)
        db.commit()
    finally:
        db.close()


def test_infected_upload_is_refused_quarantined_audited_and_never_served():
    title = "Malware test certificate"
    since = datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
    r = _external(PNG + EICAR, title)
    assert r.status_code == 422
    d = r.json()["detail"]
    assert d["code"] == "virus_found" and "not saved" in d["message"] and "வைரஸ்" in d["message_ta"]
    db = SessionLocal()
    try:
        assert db.execute(select(Certificate).where(Certificate.title == title)).first() is None       # nothing saved
        a = db.execute(select(AuditLog).where(AuditLog.action == "upload.infected", AuditLog.created_at >= since)).scalars().one()
        assert a.detail["signature"] == "Eicar-Test-Signature" and a.detail["purpose"] == "certificate_proof"
        assert len(a.detail["sha256"]) == 64 and a.college_id == "col_demo_001"
        key = a.detail["quarantine_key"]
    finally:
        db.close()
    assert key.startswith("quarantine/") and get_storage().get(key).endswith(EICAR)                    # kept for inspection
    url = sign_url(key, datetime.datetime.now() + datetime.timedelta(minutes=5))
    assert client.get("/" + url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url).status_code == 404   # never served


def test_clean_upload_is_saved():
    title = "Clean scan certificate"
    try:
        r = _external(PNG, title)
        assert r.status_code in (200, 201), r.text
    finally:
        _cleanup(title)


def test_scanner_down_means_nothing_is_saved(monkeypatch):
    class Down:
        def scan(self, data):
            raise ScannerUnavailable("clamd at clamav:3310: ConnectionRefusedError")
    monkeypatch.setattr(antivirus, "get_scanner", lambda: Down())
    title = "Scanner down certificate"
    r = _external(PNG, title)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "scanner_unavailable"
    assert "மீண்டும் முயலுங்கள்" in r.json()["detail"]["message_ta"]
    db = SessionLocal()
    try:
        assert db.execute(select(Certificate).where(Certificate.title == title)).first() is None
    finally:
        db.close()


def test_recording_and_student_import_are_scanned_too():
    db = SessionLocal()
    try:
        before = db.get(Interview, "iv_priya_2").recording_key
    finally:
        db.close()
    r = client.post("/api/v1/trainer/interviews/iv_priya_2/recording", headers=ARUN,
                    files={"file": ("round.mp4", b"\x00\x00\x00\x18ftypmp42" + EICAR, "video/mp4")})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "virus_found"
    db = SessionLocal()
    try:
        assert db.get(Interview, "iv_priya_2").recording_key == before
    finally:
        db.close()
    r = client.post("/api/v1/college/students/import?dry_run=true", headers=KAVITHA,
                    files={"file": ("students.csv", b"register_no,name\n" + EICAR, "text/csv")})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "virus_found"


# ---- the clamd protocol, against a fake daemon ----

def _fake_clamd(reply: bytes):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = {}

    def serve():
        conn, _ = srv.accept()
        data = b""
        while not data.endswith(b"\0\0\0\0"):
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        got["data"] = data
        conn.sendall(reply)
        conn.close()
        srv.close()
    threading.Thread(target=serve, daemon=True).start()
    return srv.getsockname()[1], got


@pytest.mark.parametrize("reply, clean, signature", [
    (b"stream: OK\0", True, None),
    (b"stream: Win.Test.EICAR_HDB-1 FOUND\0", False, "Win.Test.EICAR_HDB-1"),
])
def test_clamd_instream_protocol(reply, clean, signature):
    port, got = _fake_clamd(reply)
    result = ClamdScanner("127.0.0.1", port, timeout=5).scan(b"x" * 70_000)          # two chunks
    assert (result.clean, result.signature) == (clean, signature)
    assert got["data"].startswith(b"zINSTREAM\0") and got["data"].endswith(b"\0\0\0\0")


def test_clamd_errors_and_outages_fail_closed():
    port, _ = _fake_clamd(b"INSTREAM size limit exceeded. ERROR\0")
    with pytest.raises(ScannerUnavailable):
        ClamdScanner("127.0.0.1", port, timeout=5).scan(b"data")
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    free = s.getsockname()[1]
    s.close()
    with pytest.raises(ScannerUnavailable):
        ClamdScanner("127.0.0.1", free, timeout=2).scan(b"data")


@pytest.mark.skipif(os.getenv("CLAMAV_IT") != "1", reason="set CLAMAV_IT=1 with clamd on AV_CLAMD_HOST:AV_CLAMD_PORT")
def test_real_clamd_finds_eicar_and_passes_clean_files():
    scanner = ClamdScanner(os.getenv("AV_CLAMD_HOST", "127.0.0.1"), int(os.getenv("AV_CLAMD_PORT", "3310")))
    assert scanner.scan(EICAR).clean is False
    assert scanner.scan(PNG).clean is True
    assert scanner.scan(os.urandom(5 * 1024 * 1024)).clean is True                   # a 5 MB file goes through


# ---- configuration ----

def test_production_requires_clamd_and_compose_runs_it():
    from core.production import problems
    found = problems(settings.model_copy(update={"ENVIRONMENT": "production", "AV_ADAPTER": "fake"}))
    assert any("AV_ADAPTER must be clamd" in p for p in found)
    assert not any("AV_ADAPTER" in p for p in problems(settings.model_copy(update={"AV_ADAPTER": "clamd"})))
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load((REPO / "infra" / "prod" / "docker-compose.yml").read_text(encoding="utf-8"))
    assert compose["services"]["clamav"]["image"].startswith("clamav/clamav:") and "ports" not in compose["services"]["clamav"]
    assert compose["x-app"]["environment"]["AV_ADAPTER"] == "clamd"
