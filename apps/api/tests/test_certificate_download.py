"""Certificates (screens 26 and 27), Phase 2: an earned certificate downloads as a PDF, for the student and the parent."""
import sys
import uuid
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import Certificate

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, RAMESH, ARUN = _h("usr_priya_01", "student"), _h("usr_ramesh_01", "parent"), _h("usr_arun_01", "trainer")


@pytest.fixture
def certs():
    earned, pending = f"cert_t_{uuid.uuid4().hex[:8]}", f"cert_t_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(Certificate(id=earned, college_id="col_demo_001", student_id="std_priya_01", title="AWS Cloud Practitioner", issuer="AWS",
                           cert_type="external", status="earned", issued_on=datetime.date(2026, 10, 5), verify_code="IREP-X-TEST123"))
        db.add(Certificate(id=pending, college_id="col_demo_001", student_id="std_priya_01", title="Pending one", issuer="X",
                           cert_type="external", status="pending_proof"))
        db.commit()
    yield earned, pending
    with SessionLocal() as db:
        db.execute(delete(Certificate).where(Certificate.id.in_([earned, pending])))
        db.commit()


def test_student_downloads_an_earned_certificate(certs):
    earned, pending = certs
    r = client.get(f"/api/v1/student/certificates/{earned}/download", headers=PRIYA)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and b"AWS Cloud Practitioner" in r.content and b"IREP-X-TEST123" in r.content
    assert 'filename="AWS-Cloud-Practitioner.pdf"' in r.headers["content-disposition"]
    assert client.get(f"/api/v1/student/certificates/{pending}/download", headers=PRIYA).status_code == 409


def test_parent_downloads_the_childs_earned_certificate(certs):
    earned, pending = certs
    r = client.get(f"/api/v1/parent/certificates/{earned}/download", headers=RAMESH)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.get(f"/api/v1/parent/certificates/{pending}/download", headers=RAMESH).status_code == 404   # not earned: not shown to parents


def test_download_guards(certs):
    earned, _ = certs
    assert client.get(f"/api/v1/student/certificates/{earned}/download", headers=ARUN).status_code == 403
    assert client.get(f"/api/v1/student/certificates/{earned}/download", headers=_h("usr_priya_01", "student", "col_other_999")).status_code == 404
    assert client.get(f"/api/v1/student/certificates/{earned}/download", headers=_h("usr_cse_2_001_6c05", "student")).status_code == 404
