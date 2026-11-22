"""backup.sh and restore.sh with real `age`, a stand-in `docker` (no database needed).

Run: python -m pytest infra/prod/tests -q   (needs bash, age, sha256sum; CI installs age)
"""
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

PROD = Path(__file__).resolve().parents[1]
BASH = os.environ.get("BASH_FOR_TESTS") or shutil.which("bash")
AGE = shutil.which("age")
pytestmark = pytest.mark.skipif(not (BASH and AGE and shutil.which("age-keygen") and shutil.which("sha256sum")),
                                reason="needs bash, age, age-keygen and sha256sum")

# docker stand-in: dumps print fixed data; restores and the uploads tar save what they receive
FAKE_DOCKER = r'''#!/usr/bin/env bash
args="$*"
case "$args" in
  *"pg_dump -U irep -d irep "*)     printf 'PGDMP-irep-secret-student-data' ;;
  *"pg_dump -U irep -d keycloak "*) printf 'PGDMP-keycloak-users' ;;
  *"--entrypoint tar api -czf - -C /data/uploads"*)  printf 'TAR-uploads-certificates' ;;
  *"pg_restore"*"-d irep "*)        cat > "$SHIM_OUT/restored-irep" ;;
  *"pg_restore"*"-d keycloak "*)    cat > "$SHIM_OUT/restored-keycloak" ;;
  *"tar -xzf - -C /data/uploads"*)  cat > "$SHIM_OUT/restored-uploads" ;;
  *) echo "$args" >> "$SHIM_OUT/other-calls" ;;
esac
'''


@pytest.fixture
def world(tmp_path):
    """A copy of infra/prod with a .env, a key pair, and docker on PATH replaced by the stand-in."""
    work = tmp_path / "prod"
    work.mkdir()
    for name in ("backup.sh", "restore.sh"):
        shutil.copy(PROD / name, work / name)
    bins = tmp_path / "bin"
    bins.mkdir()
    (bins / "docker").write_text(FAKE_DOCKER, encoding="utf-8", newline="\n")
    (bins / "docker").chmod((bins / "docker").stat().st_mode | stat.S_IEXEC)
    key = tmp_path / "irep-backup.key"
    subprocess.run(["age-keygen", "-o", str(key)], check=True, capture_output=True)
    public = next(line.split(": ", 1)[1] for line in key.read_text().splitlines() if line.startswith("# public key:"))
    backups, out = tmp_path / "backups", tmp_path / "out"
    out.mkdir()
    env = {**os.environ, "PATH": f"{bins}{os.pathsep}{os.environ['PATH']}", "SHIM_OUT": str(out)}

    def write_env(recipient):
        (work / ".env").write_text(f"BACKUP_DIR={backups.as_posix()}\nBACKUP_KEEP_DAYS=7\nBACKUP_AGE_RECIPIENT={recipient}\n",
                                   encoding="utf-8", newline="\n")

    def run(script, *args):
        return subprocess.run([BASH, str(work / script), *args], cwd=work, env=env, capture_output=True, text=True)

    write_env(public)
    return {"run": run, "write_env": write_env, "key": key, "public": public, "backups": backups, "out": out}


def test_backup_writes_only_encrypted_files(world):
    r = world["run"]("backup.sh")
    assert r.returncode == 0, r.stderr
    folder = next(world["backups"].iterdir())
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["RECIPIENT", "SHA256SUMS", "irep.dump.age", "keycloak.dump.age", "uploads.tar.gz.age"]
    for p in folder.glob("*.age"):
        data = p.read_bytes()
        assert data.startswith(b"age-encryption.org/v1")
        assert b"secret-student-data" not in data and b"keycloak-users" not in data and b"certificates" not in data
    assert (folder / "RECIPIENT").read_text().strip() == world["public"]


@pytest.mark.parametrize("recipient", ["", "CHANGE_ME", "ssh-ed25519 AAAA"])
def test_backup_refuses_without_an_age_public_key(world, recipient):
    world["write_env"](recipient)
    r = world["run"]("backup.sh")
    assert r.returncode == 2 and "refusing to write an unencrypted backup" in r.stderr
    assert not world["backups"].exists() or not any(world["backups"].iterdir())


def test_restore_decrypts_restores_and_records_the_drill(world):
    assert world["run"]("backup.sh").returncode == 0
    folder = next(world["backups"].iterdir())
    r = world["run"]("restore.sh", str(folder), str(world["key"]))
    assert r.returncode == 0, r.stderr
    out = world["out"]
    assert (out / "restored-irep").read_text() == "PGDMP-irep-secret-student-data"
    assert (out / "restored-keycloak").read_text() == "PGDMP-keycloak-users"
    assert (out / "restored-uploads").read_text() == "TAR-uploads-certificates"
    calls = (out / "other-calls").read_text()
    assert "stop api worker beat web keycloak" in calls and "up -d" in calls
    log = [json.loads(line) for line in (world["backups"] / "restore-drills.log").read_text().splitlines()]
    assert log[-1]["kind"] == "restore" and log[-1]["backup"] == folder.name


def test_restore_refuses_a_wrong_key_or_a_damaged_backup_before_touching_anything(world, tmp_path):
    assert world["run"]("backup.sh").returncode == 0
    folder = next(world["backups"].iterdir())
    other = tmp_path / "other.key"
    subprocess.run(["age-keygen", "-o", str(other)], check=True, capture_output=True)
    r = world["run"]("restore.sh", str(folder), str(other))
    assert r.returncode == 1 and "does not decrypt" in r.stderr
    assert not (world["out"] / "other-calls").exists()                    # nothing stopped
    with open(folder / "irep.dump.age", "ab") as f:
        f.write(b"tampered")
    r = world["run"]("restore.sh", str(folder), str(world["key"]))
    assert r.returncode == 1 and "damaged" in r.stderr
    assert not (world["backups"] / "restore-drills.log").exists()
