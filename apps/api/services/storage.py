"""Object storage behind one small interface (Master Plan: S3 API everywhere; local disk is fine
for a 500-student pilot).

Every file the portal keeps goes through `get_storage()`: certificate proofs, data exports,
report and monthly-card PDFs, and recordings copied to storage. Keys are relative paths like
"certificates/col_demo_001/std_x/cert_y.png"; callers never see local paths, so moving to an
S3-compatible bucket later means implementing `S3Storage` and setting STORAGE_ADAPTER=s3,
with no change to the callers.

STORAGE_ADAPTER=local (default) keeps files under STORAGE_DIR (in production a Docker volume
that the nightly backup copies, see infra/prod/backup.sh).
"""
import mimetypes
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

_KEY = re.compile(r"^[A-Za-z0-9_\-./]+$")


def _check_key(key: str) -> str:
    if not _KEY.match(key or "") or ".." in key.split("/") or key.startswith("/"):
        raise ValueError("invalid storage key")
    return key


class Storage(ABC):
    """What callers may rely on. Implementations must reject keys that escape their root."""

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: Optional[str] = None) -> str: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def size(self, key: str) -> int: ...

    @staticmethod
    def content_type(key: str) -> str:
        return mimetypes.guess_type(key)[0] or "application/octet-stream"


class LocalStorage(Storage):
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        p = (self.root / _check_key(key)).resolve()
        if self.root not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes, content_type: Optional[str] = None) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, p)                    # readers never see a half-written file
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            p.unlink()

    def size(self, key: str) -> int:
        return self._path(key).stat().st_size


class S3Storage(Storage):
    """Placeholder for an S3-compatible bucket (E2E object storage, Cloudflare R2, AWS S3).

    Not implemented yet, on purpose: the pilot keeps files on local disk. To add it, implement the
    five methods with boto3 (put_object, get_object, head_object, delete_object, ContentLength),
    read S3_BUCKET / S3_ENDPOINT_URL / S3_ACCESS_KEY / S3_SECRET_KEY from settings, add boto3 to
    requirements.txt, and copy the existing files across before switching STORAGE_ADAPTER=s3.
    Production refuses STORAGE_ADAPTER=s3 until then (core/production.py)."""

    def __init__(self, *_, **__):
        raise NotImplementedError("S3 storage is not implemented yet; keep STORAGE_ADAPTER=local")

    def put(self, key, data, content_type=None):  # pragma: no cover
        raise NotImplementedError

    def get(self, key):  # pragma: no cover
        raise NotImplementedError

    def exists(self, key):  # pragma: no cover
        raise NotImplementedError

    def delete(self, key):  # pragma: no cover
        raise NotImplementedError

    def size(self, key):  # pragma: no cover
        raise NotImplementedError


def get_storage() -> Storage:
    if os.getenv("STORAGE_ADAPTER", "local").lower() == "s3":
        return S3Storage()
    default = Path(__file__).resolve().parent.parent / "var" / "storage"
    return LocalStorage(os.getenv("STORAGE_DIR", str(default)))
