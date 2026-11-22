"""Virus scanning for every upload, before anything is saved (ClamAV, open source).

AV_ADAPTER=clamd (production, required by core/production.py): files stream to the clamd daemon in
Docker Compose (service `clamav`, INSTREAM over TCP). AV_ADAPTER=fake (development and tests): flags
only the EICAR test file, so the infected path can be exercised without ClamAV.

`check_upload()` is the one entry point for routes:
- clean: returns, the caller saves the file;
- infected: the file goes to quarantine (`quarantine/...` in storage, never served), the event is
  audited as `upload.infected`, and the caller gets 422 with an English and Tamil message;
- scanner down: 503 (fail closed: nothing unscanned is ever saved).
"""
import datetime
import hashlib
import socket
import struct
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from core.config import settings

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
CHUNK = 64 * 1024

VIRUS_FOUND = {"code": "virus_found",
               "message": "This file contains a virus or malware and was not saved. Scan your computer and upload a clean copy.",
               "message_ta": "இந்தக் கோப்பில் வைரஸ் அல்லது தீம்பொருள் உள்ளது, சேமிக்கப்படவில்லை. உங்கள் கணினியைச் சோதித்து, சுத்தமான நகலைப் பதிவேற்றுங்கள்."}
SCANNER_DOWN = {"code": "scanner_unavailable",
                "message": "We could not check this file for viruses just now, so it was not saved. Try again in a few minutes.",
                "message_ta": "இந்தக் கோப்பை இப்போது வைரஸ் சோதனை செய்ய முடியவில்லை, எனவே சேமிக்கப்படவில்லை. சில நிமிடங்களில் மீண்டும் முயலுங்கள்."}


@dataclass
class ScanResult:
    clean: bool
    signature: Optional[str] = None


class ScannerUnavailable(RuntimeError):
    pass


class Scanner(ABC):
    @abstractmethod
    def scan(self, data: bytes) -> ScanResult: ...


class FakeScanner(Scanner):
    """Development and tests: only the EICAR test file counts as infected."""

    def scan(self, data: bytes) -> ScanResult:
        return ScanResult(False, "Eicar-Test-Signature") if EICAR in data else ScanResult(True)


class ClamdScanner(Scanner):
    """clamd INSTREAM: <length><chunk>... <0>; reply "stream: OK" or "stream: <name> FOUND"."""

    def __init__(self, host: str, port: int, timeout: float = 120.0):
        self.host, self.port, self.timeout = host, port, timeout

    def scan(self, data: bytes) -> ScanResult:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
                s.sendall(b"zINSTREAM\0")
                for i in range(0, len(data), CHUNK):
                    part = data[i:i + CHUNK]
                    s.sendall(struct.pack("!L", len(part)) + part)
                s.sendall(struct.pack("!L", 0))
                reply = b""
                while not reply.endswith(b"\0"):
                    got = s.recv(4096)
                    if not got:
                        break
                    reply += got
        except OSError as e:
            raise ScannerUnavailable(f"clamd at {self.host}:{self.port}: {e.__class__.__name__}") from e
        text = reply.rstrip(b"\0").decode("utf-8", "replace").strip()
        if text.endswith("OK"):
            return ScanResult(True)
        if text.endswith("FOUND"):
            return ScanResult(False, text.split(":", 1)[-1].strip()[: -len("FOUND")].strip() or "unknown")
        raise ScannerUnavailable(f"clamd answered: {text[:120]}")     # e.g. "INSTREAM size limit exceeded"


def get_scanner() -> Scanner:
    if settings.AV_ADAPTER.lower() == "clamd":
        return ClamdScanner(settings.AV_CLAMD_HOST, settings.AV_CLAMD_PORT)
    return FakeScanner()


def _audit(user, action: str, entity_id: Optional[str], detail: dict, college_id: str) -> None:
    """Own session: the caller's unsaved changes (a half-made certificate) are never committed here."""
    from core.database import SessionLocal
    from services.audit import record_audit
    db = SessionLocal()
    try:
        record_audit(db, user, action, "upload", entity_id, detail, college_id=college_id)
        db.commit()
    finally:
        db.close()


def check_upload(user, data: bytes, filename: Optional[str], *, college_id: str, purpose: str) -> None:
    """Scan before saving. Raises 422 (infected, quarantined) or 503 (scanner down)."""
    from services.storage import get_storage
    try:
        result = get_scanner().scan(data)
    except ScannerUnavailable as e:
        _audit(user, "upload.scan_failed", None, {"purpose": purpose, "error": str(e)[:160]}, college_id)
        raise HTTPException(status_code=503, detail=SCANNER_DOWN)
    if result.clean:
        return
    digest = hashlib.sha256(data).hexdigest()
    key = f"quarantine/{datetime.date.today().isoformat()}/{uuid.uuid4().hex}.bin"
    get_storage().put(key, data, "application/octet-stream")          # kept for inspection, never served
    _audit(user, "upload.infected", key[-40:], {"purpose": purpose, "signature": result.signature, "sha256": digest,
                                               "filename": (filename or "")[:120], "quarantine_key": key}, college_id)
    raise HTTPException(status_code=422, detail=VIRUS_FOUND)
