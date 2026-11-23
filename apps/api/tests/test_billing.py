"""S16 billing (screen 47): monthly invoices from the MoU, usage, credits and GST; numbering per
financial year; super admin only, colleges read their own. Spec: docs/screens/47-16-billing-and-dpdp.md"""
import datetime
import sys
from pathlib import Path

api_dir = str(Path(__file__).resolve().parent.parent)
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from core.database import SessionLocal
from core.security import PLATFORM_TENANT, create_access_token
from main import app
from models.schema import AuditLog, Invoice, Notification, Student, UsageLedger
from seed.seed_screen45 import seed_screen45
from services import billing

client = TestClient(app)


def _h(sub, role, cid):
    return {"Authorization": "Bearer " + create_access_token({"sub": sub, "role": role, "college_id": cid})}


SUPER = _h("usr_irep_super_01", "super_admin", PLATFORM_TENANT)
STAFF = _h("usr_irep_staff_01", "irep_admin", PLATFORM_TENANT)
KAVITHA = _h("usr_kavitha_01", "college_admin", "col_demo_001")
OTHER = _h("usr_x", "college_admin", "col_other_999")
PERIOD = datetime.date.today().strftime("%Y-%m")


@pytest.fixture(autouse=True)
def clean_billing():
    def reset():
        db = SessionLocal()
        try:
            seed_screen45(db, college_id="col_demo_001")         # no invoices, one Rs 5,000 credit
            db.execute(UsageLedger.__table__.delete().where(UsageLedger.ref_type == "billing-test"))
            db.commit()
        finally:
            db.close()
    reset()
    yield
    reset()


def _demo(r):
    return next(i for i in r["invoices"] if i["college_id"] == "col_demo_001")


def test_generate_issue_and_pay_with_the_right_money():
    db = SessionLocal()
    try:
        students = db.execute(select(func.count(Student.id)).where(Student.college_id == "col_demo_001")).scalar_one()
    finally:
        db.close()
    g = client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD}).json()
    assert g["created"] >= 1
    inv = _demo(client.get(f"/api/v1/admin/billing?period={PERIOD}", headers=SUPER).json())
    seats = next(l for l in inv["lines"] if l["kind"] == "seats")
    assert seats["quantity"] == students and seats["unit_paise"] == 37_500                 # Rs 4,500 a year / 12
    assert seats["amount_paise"] == 37_500 * students
    credit = next(l for l in inv["lines"] if l["kind"] == "credit")
    assert credit["amount_paise"] == -500_000                                             # the seeded Rs 5,000 credit
    assert inv["subtotal_paise"] == seats["amount_paise"] and inv["credit_paise"] == 500_000
    taxable = inv["subtotal_paise"] - 500_000
    assert inv["gst_paise"] == round(taxable * 0.18) and inv["total_paise"] == taxable + inv["gst_paise"]
    assert inv["status"] == "draft" and inv["number"] is None and inv["usage"]["lab_minutes"]["quota"] > 0

    out = client.post(f"/api/v1/admin/billing/invoices/{inv['id']}/issue", headers=SUPER).json()
    today = datetime.date.today()
    assert out["status"] == "issued" and out["number"] == f"IREP/{billing.financial_year(today)}/0001"
    assert out["due_on"] == (today + datetime.timedelta(days=30)).isoformat() and out["has_pdf"]
    assert client.post(f"/api/v1/admin/billing/invoices/{inv['id']}/issue", headers=SUPER).status_code == 409
    # the college sees it, its credit is used, and its admin was told in English and Tamil
    mine = client.get("/api/v1/college/billing", headers=KAVITHA).json()
    assert [i["number"] for i in mine["invoices"]] == [out["number"]] and mine["outstanding_paise"] == out["total_paise"]
    assert mine["credit_available_paise"] == 0
    pdf = client.get(f"/api/v1/college/billing/invoices/{inv['id']}/pdf", headers=KAVITHA)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and out["number"].replace("/", "-") in pdf.headers["content-disposition"]
    db = SessionLocal()
    try:
        n = db.execute(select(Notification).where(Notification.user_id == "usr_kavitha_01", Notification.link == "/college/billing")
                       .order_by(Notification.created_at.desc())).scalars().first()
        assert out["number"] in n.title_en and n.title_ta.startswith("IREP விலைப்பட்டியல்")
        assert {a for (a,) in db.execute(select(AuditLog.action).where(AuditLog.entity_id == inv["id"]))} >= {"invoice.issued"}
    finally:
        db.close()
    # regenerating does not touch an issued invoice
    assert client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD}).json()["already_issued"] >= 1
    paid = client.post(f"/api/v1/admin/billing/invoices/{inv['id']}/pay", headers=SUPER, json={"reference": "UTR123456789"}).json()
    assert paid["status"] == "paid" and paid["payment_ref"] == "UTR123456789"
    assert client.post(f"/api/v1/admin/billing/invoices/{inv['id']}/void", headers=SUPER, json={"reason": "too late"}).status_code == 409


def test_lab_and_storage_overage_are_charged_at_the_mou_rates():
    db = SessionLocal()
    try:
        from services.quotas import college_usage
        q = college_usage(db, "col_demo_001", PERIOD)["usage"]["lab_minutes"]
        extra = q["quota"] - q["used"] + 125                                              # 125 minutes over: 3 hours billed
        db.add(UsageLedger(id="ul_billing_test", college_id="col_demo_001", student_id="std_priya_01", kind="lab_minutes",
                           amount=extra, period=PERIOD, ref_type="billing-test"))
        db.commit()
    finally:
        db.close()
    client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD})
    inv = _demo(client.get(f"/api/v1/admin/billing?period={PERIOD}", headers=SUPER).json())
    lab = next(l for l in inv["lines"] if l["kind"] == "lab_overage")
    assert lab["quantity"] == 3 and lab["unit_paise"] == 2_500 and lab["amount_paise"] == 7_500


def test_void_releases_the_credit_and_frees_the_period():
    client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD})
    inv = _demo(client.get(f"/api/v1/admin/billing?period={PERIOD}", headers=SUPER).json())
    client.post(f"/api/v1/admin/billing/invoices/{inv['id']}/issue", headers=SUPER)
    assert client.get("/api/v1/college/billing", headers=KAVITHA).json()["credit_available_paise"] == 0
    v = client.post(f"/api/v1/admin/billing/invoices/{inv['id']}/void", headers=SUPER, json={"reason": "Wrong student count"}).json()
    assert v["status"] == "void"
    assert client.get("/api/v1/college/billing", headers=KAVITHA).json()["credit_available_paise"] == 500_000
    g = client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD}).json()
    assert g["created"] >= 1                                                              # a fresh draft for the same month
    again = client.post(f"/api/v1/admin/billing/invoices/{_demo_live()['id']}/issue", headers=SUPER).json()
    assert again["number"].endswith("/0002")                                              # numbers are never reused


def _demo_live():
    rows = client.get(f"/api/v1/admin/billing?period={PERIOD}", headers=SUPER).json()["invoices"]
    return next(i for i in rows if i["college_id"] == "col_demo_001" and i["status"] != "void")


def test_credits_are_added_by_the_super_admin_and_capped_by_the_subtotal():
    r = client.post("/api/v1/admin/billing/credits", headers=SUPER, json={"college_id": "col_demo_001", "amount_inr": 99_999_99 / 100 * 100,
                                                                          "reason": "Prepayment for the year"})
    assert r.status_code == 201
    client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD})
    inv = _demo(client.get(f"/api/v1/admin/billing?period={PERIOD}", headers=SUPER).json())
    assert inv["credit_paise"] == inv["subtotal_paise"] and inv["gst_paise"] == 0 and inv["total_paise"] == 0
    assert client.post("/api/v1/admin/billing/credits", headers=SUPER, json={"college_id": "col_nope", "amount_inr": 10,
                                                                             "reason": "nowhere"}).status_code == 404


def test_numbering_follows_the_indian_financial_year():
    assert billing.financial_year(datetime.date(2027, 3, 31)) == "2026-27"
    assert billing.financial_year(datetime.date(2027, 4, 1)) == "2027-28"
    assert billing.rupees(1_234_567) == "Rs 12,345.67" and billing.rupees(-50) == "-Rs 0.50"


def test_only_the_super_admin_bills_and_colleges_see_only_their_own():
    for h in (STAFF, KAVITHA):
        assert client.get("/api/v1/admin/billing", headers=h).status_code == 403
        assert client.post("/api/v1/admin/billing/generate", headers=h, json={"period": PERIOD}).status_code == 403
    client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD})
    inv = _demo(client.get(f"/api/v1/admin/billing?period={PERIOD}", headers=SUPER).json())
    assert client.get(f"/api/v1/college/billing/invoices/{inv['id']}/pdf", headers=KAVITHA).status_code == 404   # a draft is not visible
    client.post(f"/api/v1/admin/billing/invoices/{inv['id']}/issue", headers=SUPER)
    assert client.get(f"/api/v1/college/billing/invoices/{inv['id']}/pdf", headers=OTHER).status_code == 404     # other college
    assert client.get("/api/v1/college/billing", headers=OTHER).json()["invoices"] == []
    assert client.get("/api/v1/college/billing", headers=STAFF).status_code == 403


def test_invoice_lines_in_tamil():
    client.post("/api/v1/admin/billing/generate", headers=SUPER, json={"period": PERIOD})
    inv = _demo(client.get(f"/api/v1/admin/billing?period={PERIOD}&lang=ta", headers=SUPER).json())
    assert next(l for l in inv["lines"] if l["kind"] == "seats")["label"].startswith("IREP திட்ட இடங்கள்")
    assert next(l for l in inv["lines"] if l["kind"] == "credit")["label"].startswith("வரவு:")


@pytest.mark.skipif(not str(SessionLocal.kw["bind"].url).startswith("postgresql"), reason="row locks need PostgreSQL")
def test_two_invoices_issued_at_once_spend_a_credit_only_once():
    """Two issuers race for the same Rs 5,000 credit: together they may use it once, never twice."""
    import threading
    from models.schema import BillingCredit
    other = (datetime.date.fromisoformat(PERIOD + "-01") - datetime.timedelta(days=1)).strftime("%Y-%m")
    db = SessionLocal()
    try:
        billing.generate(db, PERIOD)
        billing.generate(db, other)
        db.commit()
        ids = [db.execute(select(Invoice.id).where(Invoice.college_id == "col_demo_001", Invoice.period == p,
                                                   Invoice.status == "draft")).scalar_one() for p in (PERIOD, other)]
    finally:
        db.close()
    start, errors = threading.Barrier(2), []

    def issue(invoice_id):
        s = SessionLocal()
        try:
            inv = s.get(Invoice, invoice_id)
            start.wait()
            billing.issue(s, inv)
            s.commit()
        except Exception as e:             # noqa: BLE001  reported below
            errors.append(e)
            s.rollback()
        finally:
            s.close()
    threads = [threading.Thread(target=issue, args=(i,)) for i in ids]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    assert not errors, errors
    db = SessionLocal()
    try:
        credits = db.execute(select(func.sum(Invoice.credit_paise)).where(Invoice.id.in_(ids))).scalar_one()
        used = db.execute(select(func.sum(BillingCredit.used_paise)).where(BillingCredit.college_id == "col_demo_001")).scalar_one()
        assert credits == 500_000 and used == 500_000
    finally:
        db.close()
