"""Screens 26, 27, 28 and the 43 proof decision: links L10, L32, L35.
Spec: docs/screens/26-27-28-certificates.md"""
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from core.database import SessionLocal
from core.security import create_access_token
from main import app
from models.schema import AuditLog, Notification

client = TestClient(app)


def _h(sub, role, college_id="col_demo_001"):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": college_id, "name": sub})}


PRIYA, ARUN, MEENA = _h("usr_priya_01", "student"), _h("usr_arun_01", "trainer"), _h("usr_meena_01", "trainer")
RAMESH, KAVITHA = _h("usr_ramesh_01", "parent"), _h("usr_kavitha_01", "college_admin")
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200
PDF = b"%PDF-1.4\n%demo proof\n"


@pytest.fixture(autouse=True)
def restore():
    yield
    from seed.seed_screen49 import seed_screen49
    db = SessionLocal()
    try:
        seed_screen49(db)
        db.commit()
    finally:
        db.close()


def _add(title="Oracle Java SE Foundations", data=PNG, issued_on="2026-11-01"):
    return client.post("/api/v1/student/certificates", data={"title": title, "issuer": "Oracle", "issued_on": issued_on, "credential_id": "OCJ-123"},
                       files={"file": ("proof.png", data, "image/png")}, headers=PRIYA)


@pytest.mark.link("L10")
@pytest.mark.link("L32")
def test_proof_goes_up_and_only_an_approved_certificate_reaches_the_parent():
    r = _add()
    assert r.status_code == 201 and r.json()["status"] == "pending_proof" and not r.json()["verified"]
    cid = r.json()["id"]
    parent = client.get("/api/v1/parent/certificates", headers=RAMESH).json()
    assert all(c["id"] != cid for c in parent["earned"])                                     # release rule: not yet
    queue = client.get("/api/v1/trainer/approvals?status=pending", headers=ARUN).json()
    item = next(i for i in queue["items"] if i["type"] == "certificate" and i["id"] == cid)
    assert item["student_name"] == "Priya R" and item["detail"]["credential_id"] == "OCJ-123" and queue["counts"]["certificate"] >= 1
    proof = client.get(f"/api/v1/trainer/certificates/{cid}/proof", headers=ARUN)
    assert proof.status_code == 200 and proof.headers["content-type"] == "image/png" and proof.content == PNG
    assert client.get(f"/api/v1/trainer/certificates/{cid}/proof", headers=MEENA).status_code == 404            # not her batch

    ok = client.post(f"/api/v1/trainer/approvals/certificates/{cid}", json={"decision": "approve"}, headers=ARUN)
    assert ok.status_code == 200 and ok.json()["verified"] and ok.json()["verify_code"].startswith("IREP-X-")
    assert client.post(f"/api/v1/trainer/approvals/certificates/{cid}", json={"decision": "approve"}, headers=ARUN).status_code == 409
    earned = client.get("/api/v1/parent/certificates?lang=ta", headers=RAMESH).json()["earned"]
    row = next(c for c in earned if c["id"] == cid)
    assert row["status_label"] == "சரிபார்க்கப்பட்டது" and row["has_proof"] is None                        # no proof files for parents
    db = SessionLocal()
    try:
        for action in ("certificate_proof.submitted", "certificate_proof.viewed", "certificate_proof.decided"):
            assert db.execute(select(AuditLog).where(AuditLog.action == action, AuditLog.entity_id == cid)).first(), action
        assert db.execute(select(Notification).where(Notification.user_id == "usr_ramesh_01", Notification.link == "/parent/certificates")).first()
        assert db.execute(select(Notification).where(Notification.user_id == "usr_arun_01", Notification.link == "/trainer/approvals",
                                                     Notification.body_en == "Oracle Java SE Foundations")).first()
    finally:
        db.close()


def test_rejection_needs_a_note_and_the_student_can_resubmit():
    cid = _add(data=PDF).json()["id"]
    assert client.post(f"/api/v1/trainer/approvals/certificates/{cid}", json={"decision": "deny"}, headers=ARUN).status_code == 422
    r = client.post(f"/api/v1/trainer/approvals/certificates/{cid}", json={"decision": "deny", "note": "The name on the proof is cut off"}, headers=ARUN)
    assert r.json()["status"] == "rejected"
    mine = next(c for c in client.get("/api/v1/student/certificates", headers=PRIYA).json()["certificates"] if c["id"] == cid)
    assert mine["decision_note"] == "The name on the proof is cut off"
    again = client.post(f"/api/v1/student/certificates/{cid}/proof", files={"file": ("p.pdf", PDF, "application/pdf")}, headers=PRIYA)
    assert again.status_code == 200 and again.json()["status"] == "pending_proof"
    assert client.get(f"/api/v1/student/certificates/{cid}/proof", headers=PRIYA).content == PDF


def test_scheduled_exam_proof_and_upload_guards():
    r = client.post("/api/v1/student/certificates/cert_priya_aws_sched/proof", files={"file": ("score.png", PNG, "image/png")}, headers=PRIYA)
    assert r.status_code == 200 and r.json()["status"] == "pending_proof" and r.json()["voucher"]
    assert _add(data=b"hello, not a file").status_code == 422
    assert _add(data=b"%PDF" + b"0" * (5 * 1024 * 1024)).status_code == 413
    assert _add(issued_on="2099-01-01").status_code == 422
    assert client.get("/api/v1/student/certificates", headers=ARUN).status_code == 403
    assert client.post("/api/v1/trainer/approvals/certificates/cert_priya_aws_sched", json={"decision": "maybe"}, headers=ARUN).status_code == 422
    other = _h("usr_arun_01", "trainer", "col_other_test")
    assert client.post("/api/v1/trainer/approvals/certificates/cert_priya_aws_sched", json={"decision": "approve"}, headers=other).status_code in (403, 404)


def test_parent_copy_needs_consent():
    client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "withdrawn", "student_id": "std_priya_01"}, headers=RAMESH)
    try:
        assert client.get("/api/v1/parent/certificates", headers=RAMESH).json()["consent_required"] is True
    finally:
        client.post("/api/v1/consent", json={"purpose": "parent_data_processing", "status": "granted", "student_id": "std_priya_01"}, headers=RAMESH)
    assert client.get("/api/v1/parent/certificates", headers=RAMESH).json()["upcoming"][0]["title"] == "AWS Cloud Practitioner"


@pytest.mark.link("L35")
def test_college_sees_counts_only():
    _add()
    d = client.get("/api/v1/college/certifications", headers=KAVITHA).json()
    assert d["totals"]["earned"] >= 184 and d["totals"]["proofs_pending"] >= 1 and d["totals"]["scheduled_exams"] >= 1
    assert d["vouchers"]["issued"] >= 1 and d["issuers"] and d["batches"] and d["monthly"]
    assert "Priya" not in str(d) and "OCJ-123" not in str(d)
    assert client.get("/api/v1/college/certifications", headers=PRIYA).status_code == 403
