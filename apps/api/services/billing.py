"""S16 billing (screen 47): monthly invoices per college from the MoU, metered usage and credits.
Spec: docs/screens/47-16-billing-and-dpdp.md. Every amount is an integer number of paise.

- Seats: students enrolled now x MoU fee_per_student_inr / 12 (the fee is per academic year).
- Lab hours and recording storage over the MoU quota (L36), at the MoU's overage rates (0 = free).
- Usage this month is shown for information (lab minutes, AI calls, MB against quota).
- Credits reduce the subtotal; GST (BILLING_GST_PCT) is on the remainder.
- Drafts are refreshed by `generate`; issuing fixes the lines, takes credits, numbers the invoice in
  the financial year (April-March: IREP/2026-27/0001), stores the PDF and tells the college admins.
"""
import datetime
import math
import uuid
from typing import List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import settings
from core.security import PLATFORM_TENANT
from models.schema import BillingCredit, College, Invoice, InvoiceLine, User
from services.quotas import active_mou, college_usage

PERIOD_FMT = "%Y-%m"


def rupees(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    p = abs(int(paise))
    return f"{sign}Rs {p // 100:,}.{p % 100:02d}"


def financial_year(d: datetime.date) -> str:
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def _period_label(period: str) -> str:
    return datetime.datetime.strptime(period, PERIOD_FMT).strftime("%B %Y")


def credit_available(db: Session, college_id: str) -> int:
    return int(db.execute(select(func.coalesce(func.sum(BillingCredit.amount_paise - BillingCredit.used_paise), 0))
                          .where(BillingCredit.college_id == college_id)).scalar_one())


def _charge_lines(db: Session, college_id: str, period: str) -> tuple:
    """(lines without credit, students, usage) for one college and month."""
    mou = active_mou(db, college_id)
    use = college_usage(db, college_id, period)
    students = use["students"]
    month = _period_label(period)
    lines: List[dict] = []
    if mou and mou.fee_per_student_inr:
        unit = round(mou.fee_per_student_inr * 100 / 12)
        lines.append({"kind": "seats", "label_en": f"IREP programme seats, {month} ({students} students x 1/12 of the yearly fee)",
                      "label_ta": f"IREP திட்ட இடங்கள், {month} ({students} மாணவர்கள் x ஆண்டுக் கட்டணத்தின் 1/12)",
                      "quantity": students, "unit_paise": unit, "amount_paise": unit * students})
    lab = use["usage"]["lab_minutes"]
    over_h = math.ceil(max(0, lab["used"] - lab["quota"]) / 60) if lab["quota"] is not None else 0
    if mou and over_h and mou.lab_overage_inr_per_hour:
        unit = mou.lab_overage_inr_per_hour * 100
        lines.append({"kind": "lab_overage", "label_en": f"Lab hours over the MoU quota ({over_h} h)",
                      "label_ta": f"ஒப்பந்த வரம்பை மீறிய ஆய்வக மணிநேரம் ({over_h} மணி)",
                      "quantity": over_h, "unit_paise": unit, "amount_paise": unit * over_h})
    rec = use["usage"]["recording_mb"]
    over_gb = math.ceil(max(0, rec["used"] - rec["quota"]) / 1024) if rec["quota"] is not None else 0
    if mou and over_gb and mou.storage_overage_inr_per_gb:
        unit = mou.storage_overage_inr_per_gb * 100
        lines.append({"kind": "storage_overage", "label_en": f"Recording storage over the MoU quota ({over_gb} GB)",
                      "label_ta": f"ஒப்பந்த வரம்பை மீறிய பதிவுச் சேமிப்பு ({over_gb} GB)",
                      "quantity": over_gb, "unit_paise": unit, "amount_paise": unit * over_gb})
    usage = {k: {"used": v["used"], "quota": v["quota"]} for k, v in use["usage"].items()}
    return lines, students, usage, mou


def _set_lines(db: Session, inv: Invoice, lines: List[dict]) -> None:
    db.execute(delete(InvoiceLine).where(InvoiceLine.invoice_id == inv.id))
    db.flush()
    for i, ln in enumerate(lines):
        db.add(InvoiceLine(id=f"invl_{uuid.uuid4().hex[:14]}", college_id=inv.college_id, invoice_id=inv.id, position=i,
                           kind=ln["kind"], label_en=ln["label_en"], label_ta=ln["label_ta"], quantity=ln["quantity"],
                           unit_paise=ln["unit_paise"], amount_paise=ln["amount_paise"], credit_id=ln.get("credit_id")))


def _totals(inv: Invoice, lines: List[dict]) -> None:
    inv.subtotal_paise = sum(ln["amount_paise"] for ln in lines if ln["kind"] != "credit")
    inv.credit_paise = -sum(ln["amount_paise"] for ln in lines if ln["kind"] == "credit")
    taxable = inv.subtotal_paise - inv.credit_paise
    inv.gst_pct = settings.BILLING_GST_PCT
    inv.gst_paise = round(taxable * inv.gst_pct / 100)
    inv.total_paise = taxable + inv.gst_paise


def _credit_lines(db: Session, college_id: str, subtotal: int, *, take: bool) -> List[dict]:
    """Credits oldest first, up to the subtotal. take=True marks them used (on issue)."""
    out, left = [], subtotal
    for c in db.execute(select(BillingCredit).where(BillingCredit.college_id == college_id,
                                                    BillingCredit.used_paise < BillingCredit.amount_paise)
                        .order_by(BillingCredit.created_at, BillingCredit.id)).scalars():
        if left <= 0:
            break
        use = min(left, c.amount_paise - c.used_paise)
        left -= use
        if take:
            c.used_paise += use
        out.append({"kind": "credit", "label_en": f"Credit: {c.reason[:80]}", "label_ta": f"வரவு: {c.reason[:80]}",
                    "quantity": 1, "unit_paise": -use, "amount_paise": -use, "credit_id": c.id})
    return out


def generate(db: Session, period: str) -> dict:
    """Create or refresh the drafts of `period` for every college with an active MoU."""
    datetime.datetime.strptime(period, PERIOD_FMT)
    made = refreshed = skipped = 0
    for c in db.execute(select(College).where(College.id != PLATFORM_TENANT).order_by(College.name)).scalars():
        lines, students, usage, mou = _charge_lines(db, c.id, period)
        if mou is None:
            continue
        inv = db.execute(select(Invoice).where(Invoice.college_id == c.id, Invoice.period == period,
                                               Invoice.status_key == "live")).scalar_one_or_none()
        if inv is not None and inv.status != "draft":
            skipped += 1
            continue
        if inv is None:
            inv = Invoice(id=f"inv_{uuid.uuid4().hex[:14]}", college_id=c.id, period=period, status="draft", status_key="live")
            db.add(inv)
            db.flush()
            made += 1
        else:
            refreshed += 1
        subtotal = sum(ln["amount_paise"] for ln in lines)
        all_lines = lines + _credit_lines(db, c.id, subtotal, take=False)          # preview; taken on issue
        inv.mou_id, inv.students, inv.usage = mou.id, students, usage
        _set_lines(db, inv, all_lines)
        _totals(inv, all_lines)
    return {"period": period, "created": made, "refreshed": refreshed, "already_issued": skipped}


def lines_of(db: Session, inv: Invoice) -> List[InvoiceLine]:
    return db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)).scalars().all()


def _next_number(db: Session, when: datetime.date) -> str:
    prefix = f"IREP/{financial_year(when)}/"
    last = db.execute(select(func.max(Invoice.number)).where(Invoice.number.like(prefix + "%"))).scalar_one()
    n = int(last.rsplit("/", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


def _pdf(db: Session, inv: Invoice, college: College) -> bytes:
    from services.reports import render_pdf
    rows = [f"Invoice {inv.number}  ·  {college.name}", f"Period: {_period_label(inv.period)}",
            f"Issued: {inv.issued_at:%d %b %Y}  ·  Due: {inv.due_on:%d %b %Y}", ""]
    for ln in lines_of(db, inv):
        rows.append(f"{ln.label_en}: {rupees(ln.amount_paise)}")
    rows += ["", f"Subtotal: {rupees(inv.subtotal_paise)}", f"Credits: -{rupees(inv.credit_paise)}",
             f"GST {inv.gst_pct:g}%: {rupees(inv.gst_paise)}", f"Total due: {rupees(inv.total_paise)}", "",
             "Usage this month: " + ", ".join(f"{k.replace('_', ' ')} {v['used']} of {v['quota'] if v['quota'] is not None else '-'}"
                                             for k, v in (inv.usage or {}).items())]
    return render_pdf(f"IREP invoice {inv.number}", [r.encode("ascii", "replace").decode() for r in rows])


def issue(db: Session, inv: Invoice) -> List[str]:
    """Fix the lines, take credits, number, PDF, due date. Returns the college admins' user ids."""
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"Only a draft can be issued (this invoice is {inv.status})")
    charges = [{"kind": ln.kind, "label_en": ln.label_en, "label_ta": ln.label_ta, "quantity": ln.quantity,
                "unit_paise": ln.unit_paise, "amount_paise": ln.amount_paise} for ln in lines_of(db, inv) if ln.kind != "credit"]
    if not charges:
        raise HTTPException(status_code=422, detail="Nothing to bill: the MoU has no fee and no overage this month")
    all_lines = charges + _credit_lines(db, inv.college_id, sum(c["amount_paise"] for c in charges), take=True)
    _set_lines(db, inv, all_lines)
    _totals(inv, all_lines)
    now = datetime.datetime.utcnow()
    inv.issued_at, inv.due_on, inv.status = now, now.date() + datetime.timedelta(days=30), "issued"
    for attempt in range(3):                          # the unique number decides a race between two issuers
        inv.number = _next_number(db, now.date())
        try:
            with db.begin_nested():
                db.flush()
            break
        except IntegrityError:
            if attempt == 2:
                raise
    college = db.get(College, inv.college_id)
    from services.storage import get_storage
    inv.pdf_key = f"invoices/{inv.college_id}/{inv.id}.pdf"
    get_storage().put(inv.pdf_key, _pdf(db, inv, college), "application/pdf")
    return list(db.execute(select(User.id).where(User.college_id == inv.college_id, User.role == "college_admin",
                                                 User.is_active.is_(True))).scalars())


def mark_paid(inv: Invoice, reference: str) -> None:
    if inv.status != "issued":
        raise HTTPException(status_code=409, detail=f"Only an issued invoice can be marked paid (this one is {inv.status})")
    inv.status, inv.paid_at, inv.payment_ref = "paid", datetime.datetime.utcnow(), reference.strip()


def void(db: Session, inv: Invoice, reason: str) -> None:
    if inv.status in ("void", "paid"):
        raise HTTPException(status_code=409, detail=f"A {inv.status} invoice cannot be voided")
    for ln in lines_of(db, inv):
        if ln.kind == "credit" and ln.credit_id and inv.status == "issued":
            c = db.get(BillingCredit, ln.credit_id)
            if c is not None:
                c.used_paise = max(0, c.used_paise + ln.amount_paise)          # amount is negative: give it back
    inv.status, inv.void_reason, inv.status_key = "void", reason.strip(), inv.id   # frees the period for a new invoice


def invoice_out(db: Session, inv: Invoice, lang: str = "en", names: Optional[dict] = None) -> dict:
    ta = lang == "ta"
    return {"id": inv.id, "college_id": inv.college_id, "college": (names or {}).get(inv.college_id), "period": inv.period,
            "number": inv.number, "status": inv.status, "students": inv.students,
            "subtotal_paise": inv.subtotal_paise, "credit_paise": inv.credit_paise, "gst_pct": inv.gst_pct,
            "gst_paise": inv.gst_paise, "total_paise": inv.total_paise, "usage": inv.usage or {},
            "issued_at": inv.issued_at.isoformat() if inv.issued_at else None, "due_on": inv.due_on.isoformat() if inv.due_on else None,
            "paid_at": inv.paid_at.isoformat() if inv.paid_at else None, "payment_ref": inv.payment_ref, "void_reason": inv.void_reason,
            "has_pdf": bool(inv.pdf_key),
            "lines": [{"kind": ln.kind, "label": ln.label_ta if ta else ln.label_en, "quantity": ln.quantity,
                       "unit_paise": ln.unit_paise, "amount_paise": ln.amount_paise} for ln in lines_of(db, inv)]}
