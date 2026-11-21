"""Object storage behind one small interface (Master Plan: S3 API everywhere;
R2 in the demo, E2E object storage in India for the pilot).

STORAGE_ADAPTER=local (default) keeps files under STORAGE_DIR; an S3-compatible
adapter plugs in here for the pilot. Keys are relative paths like
"exports/col_demo_001/dr_x.json"; callers never see local paths.
"""
import os
import re
from pathlib import Path

_KEY = re.compile(r"^[A-Za-z0-9_\-./]+$")


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        if not _KEY.match(key) or ".." in key.split("/"):
            raise ValueError("invalid storage key")
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("invalid storage key")
        return p

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


def get_storage() -> LocalStorage:
    default = Path(__file__).resolve().parent.parent / "var" / "storage"
    return LocalStorage(os.getenv("STORAGE_DIR", str(default)))
