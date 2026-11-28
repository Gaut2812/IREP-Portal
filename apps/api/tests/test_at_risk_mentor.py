"""Screen 14 (Phase 3): notify parent again after 3 days, log a phone call, assign a mentor, My mentees."""
import datetime

from sqlalchemy import delete, select

from core.database import SessionLocal
from models.schema import AtRiskFlag, AuditLog, Notification
from tests.test_screen_42_17_14 import ARUN, MEENA, PRIYA, _h, client, priya_flag  # noqa: F401 (fixture)


def _cleanup_mentor_notes(started):
    db = SessionLocal()
    try:
        db.execute(delete(Notification).where(Notification.created_at >= started, Notification.title_en.contains("mentor")))
        db.commit()
    finally:
        db.close()


def test_phone_call_needs_an_outcome_and_is_kept(priya_flag):
    url = f"/api/v1/trainer/flags/{priya_flag}/actions"
    assert client.post(url, json={"action_type": "phone_call"}, headers=ARUN).status_code == 422
    assert client.post(url, json={"action_type": "mentor"}, headers=ARUN).status_code == 422          # now its own endpoint
    r = client.post(url, json={"action_type": "phone_call", "outcome": "no_answer", "note": "  try after 6 pm "}, headers=ARUN)
    assert r.status_code == 200 and r.json()["status"] == "in_progress" and r.json()["parent_call"] is None
    hist = client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=ARUN).json()
    assert hist["actions"][-1] == {**hist["actions"][-1], "type": "phone_call", "note": "No answer: try after 6 pm"}


def test_parent_can_be_notified_again_after_three_days(priya_flag):
    url = f"/api/v1/trainer/flags/{priya_flag}/actions"
    assert client.post(url, json={"action_type": "parent_call"}, headers=ARUN).json()["parent_call"] == "sent"
    first = client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=ARUN).json()["parent_notified_at"]
    assert first and client.post(url, json={"action_type": "parent_call"}, headers=ARUN).json()["parent_call"] == "already"
    db = SessionLocal()
    try:
        flag = db.get(AtRiskFlag, priya_flag)
        flag.parent_notified_at = datetime.datetime.utcnow() - datetime.timedelta(days=4)
        db.commit()
    finally:
        db.close()
    assert client.post(url, json={"action_type": "parent_call"}, headers=ARUN).json()["parent_call"] == "sent"
    row = next(f for f in client.get("/api/v1/trainer/at-risk", headers=ARUN).json()["flags"] if f["id"] == priya_flag)
    assert row["parent_notified_at"] > first


def test_assign_mentor_notifies_and_lists_the_mentee(priya_flag):
    started = datetime.datetime.utcnow() - datetime.timedelta(seconds=2)
    try:
        mentors = client.get("/api/v1/trainer/mentors", headers=ARUN).json()["mentors"]
        assert mentors[0]["user_id"] == "usr_arun_01" and mentors[0]["is_me"]
        assert any(m["user_id"] == "usr_meena_01" for m in mentors)

        r = client.post(f"/api/v1/trainer/flags/{priya_flag}/mentor", json={"user_id": "usr_meena_01"}, headers=ARUN)
        assert r.status_code == 200 and r.json()["mentor"]["user_id"] == "usr_meena_01" and r.json()["status"] == "in_progress"

        # Meena mentors Priya even though the batch is not hers: she sees and can open the flag
        mentees = client.get("/api/v1/trainer/mentees?lang=ta", headers=MEENA).json()["mentees"]
        assert [m["flag_id"] for m in mentees] == [priya_flag] and mentees[0]["issue"] == "வருகை 68%"
        assert client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=MEENA).status_code == 200
        assert client.get("/api/v1/trainer/mentees", headers=ARUN).json()["mentees"] == []

        db = SessionLocal()
        try:
            to_meena = db.execute(select(Notification).where(Notification.user_id == "usr_meena_01", Notification.created_at >= started,
                                                             Notification.channel == "in_app")).scalars().all()
            to_priya = db.execute(select(Notification).where(Notification.user_id == "usr_priya_01", Notification.created_at >= started,
                                                             Notification.channel == "in_app")).scalars().all()
            assert any("mentoring" in n.title_en and n.title_ta for n in to_meena)
            assert any("your mentor" in n.title_en for n in to_priya)
            assert db.execute(select(AuditLog).where(AuditLog.action == "at_risk.mentor", AuditLog.entity_id == priya_flag)).first()
        finally:
            db.close()

        listed = next(f for f in client.get("/api/v1/trainer/at-risk", headers=ARUN).json()["flags"] if f["id"] == priya_flag)
        assert listed["mentor"]["user_id"] == "usr_meena_01" and listed["mentor"]["name"]

        # remove the mentor: history keeps both steps, Meena loses access again
        assert client.post(f"/api/v1/trainer/flags/{priya_flag}/mentor", json={"user_id": None}, headers=ARUN).json()["mentor"] is None
        assert client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=MEENA).status_code == 404
        notes = [a["note"] for a in client.get(f"/api/v1/trainer/flags/{priya_flag}", headers=ARUN).json()["actions"] if a["type"] == "mentor"]
        assert len(notes) == 2 and notes[1] == "Mentor removed"
    finally:
        _cleanup_mentor_notes(started)


def test_mentor_guards(priya_flag):
    url = f"/api/v1/trainer/flags/{priya_flag}/mentor"
    assert client.post(url, json={"user_id": "usr_meena_01"}, headers=PRIYA).status_code == 403
    assert client.get("/api/v1/trainer/mentees", headers=PRIYA).status_code == 403
    assert client.post(url, json={"user_id": "usr_priya_01"}, headers=ARUN).status_code == 404      # not a trainer
    assert client.post(url, json={"user_id": "usr_meena_01"}, headers=MEENA).status_code == 404     # not her batch
    other = _h("usr_arun_01", "trainer", "col_other_test")
    assert client.post(url, json={"user_id": "usr_meena_01"}, headers=other).status_code in (403, 404)
