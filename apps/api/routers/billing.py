"""S16 · Billing (screen 47, full). Super admin: generate, issue, settle, void, credits. College admin:
own issued invoices, credit balance and PDFs. Spec: docs/screens/47-16-billing-and-dpdp.md"""
import datetime
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import PLATFORM_TENANT, SUPER, TokenPayload, require_role
from models.schema import BillingCredit, College, Invoice
from services import billing as svc
from services.audit import record_audit
from services.notifications import notify_user
from services.storage import get_storage

router = APIRouter(tags=["S16 · Billing"])
COLLEGE = require_role(["college_admin"])
PERIOD = r"^\d{4}-(0[1-9]|1[0-2])$"


class GenerateIn(BaseModel):
    period: str = Field(pattern=PERIOD)


class PayIn(BaseModel):
    reference: str = Field(min_length=3, max_length=64)


class VoidIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class CreditIn(BaseModel):
    college_id: str = Field(min_length=1, max_length=64)
    amount_inr: float = Field(gt=0, le=10_000_000)
    reason: str = Field(min_length=5, max_length=255)


def _names(db: Session) -> dict:
    return dict(db.execute(select(College.id, College.name)).all())


def _invoice(db: Session, invoice_id: str, college_id: Optional[str] = None) -> Invoice:
    inv = db.get(Invoice, invoice_id)
    if inv is None or (college_id is not None and inv.college_id != college_id):
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


def _pdf(inv: Invoice) -> Response:
    if not inv.pdf_key or not get_storage().exists(inv.pdf_key):
        raise HTTPException(status_code=404, detail="This invoice has no PDF yet (it is issued with one)")
    name = (inv.number or inv.id).replace("/", "-")
    return Response(content=get_storage().get(inv.pdf_key), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


# ---------------------------------------------------------------- super admin

@router.get("/admin/billing")
def billing_overview(period: Optional[str] = Query(None, pattern=PERIOD), lang: str = "en",
                     current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    period = period or datetime.date.today().strftime("%Y-%m")
    names = _names(db)
    rows = db.execute(select(Invoice).where(Invoice.period == period).order_by(Invoice.status_key, Invoice.created_at)).scalars().all()
    credits = db.execute(select(BillingCredit).order_by(BillingCredit.created_at.desc()).limit(100)).scalars().all()
    totals = {s: sum(i.total_paise for i in rows if i.status == s) for s in ("draft", "issued", "paid")}
    return {"period": period, "invoices": [svc.invoice_out(db, i, lang, names) for i in rows], "totals_paise": totals,
            "credits": [{"id": c.id, "college_id": c.college_id, "college": names.get(c.college_id), "amount_paise": c.amount_paise,
                         "used_paise": c.used_paise, "reason": c.reason, "created_at": c.created_at.isoformat()} for c in credits],
            "colleges": [{"id": k, "name": v} for k, v in sorted(names.items(), key=lambda kv: kv[1]) if k != PLATFORM_TENANT]}


@router.post("/admin/billing/generate")
def generate(req: GenerateIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    out = svc.generate(db, req.period)
    record_audit(db, current_user, "invoice.generated", "billing", req.period, out, college_id=PLATFORM_TENANT)
    db.commit()
    return out


@router.get("/admin/billing/invoices/{invoice_id}")
def get_invoice(invoice_id: str, lang: str = "en", current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    return svc.invoice_out(db, _invoice(db, invoice_id), lang, _names(db))


@router.post("/admin/billing/invoices/{invoice_id}/issue")
def issue(invoice_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id)
    admins = svc.issue(db, inv)
    total = svc.rupees(inv.total_paise)
    for uid in admins:
        notify_user(db, uid, f"Invoice {inv.number} from IREP", f"{total}, due {inv.due_on:%d %b %Y}. Open Billing to download it.",
                    title_ta=f"IREP விலைப்பட்டியல் {inv.number}", body_ta=f"{total}, கடைசி நாள் {inv.due_on:%d-%m-%Y}. பதிவிறக்க பில்லிங்கைத் திறக்கவும்.",
                    kind="info", link="/college/billing", college_id=inv.college_id)
    record_audit(db, current_user, "invoice.issued", "invoice", inv.id, {"number": inv.number, "total_paise": inv.total_paise},
                 college_id=inv.college_id)
    db.commit()
    return svc.invoice_out(db, inv, "en", _names(db))


@router.post("/admin/billing/invoices/{invoice_id}/pay")
def pay(invoice_id: str, req: PayIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id)
    svc.mark_paid(inv, req.reference)
    record_audit(db, current_user, "invoice.paid", "invoice", inv.id, {"number": inv.number, "reference": inv.payment_ref},
                 college_id=inv.college_id)
    db.commit()
    return svc.invoice_out(db, inv, "en", _names(db))


@router.post("/admin/billing/invoices/{invoice_id}/void")
def void(invoice_id: str, req: VoidIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id)
    svc.void(db, inv, req.reason)
    record_audit(db, current_user, "invoice.voided", "invoice", inv.id, {"number": inv.number, "reason": inv.void_reason},
                 college_id=inv.college_id)
    db.commit()
    return svc.invoice_out(db, inv, "en", _names(db))


@router.get("/admin/billing/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: str, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    return _pdf(_invoice(db, invoice_id))


@router.post("/admin/billing/credits", status_code=201)
def add_credit(req: CreditIn, current_user: TokenPayload = Depends(SUPER), db: Session = Depends(get_db)):
    c = db.get(College, req.college_id)
    if c is None or c.id == PLATFORM_TENANT:
        raise HTTPException(status_code=404, detail="College not found")
    cr = BillingCredit(id=f"cred_{uuid.uuid4().hex[:14]}", college_id=c.id, amount_paise=round(req.amount_inr * 100),
                       used_paise=0, reason=req.reason.strip(), created_by=current_user.sub)
    db.add(cr)
    record_audit(db, current_user, "billing.credit_added", "billing_credit", cr.id, {"amount_paise": cr.amount_paise, "reason": cr.reason},
                 college_id=c.id)
    db.commit()
    return {"id": cr.id, "college_id": c.id, "amount_paise": cr.amount_paise, "available_paise": svc.credit_available(db, c.id)}


# ---------------------------------------------------------------- college admin

@router.get("/college/billing")
def my_billing(lang: str = "en", current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    rows = db.execute(select(Invoice).where(Invoice.college_id == current_user.college_id, Invoice.status.in_(("issued", "paid", "void")))
                      .order_by(Invoice.period.desc(), Invoice.issued_at.desc())).scalars().all()
    return {"invoices": [svc.invoice_out(db, i, lang) for i in rows],
            "outstanding_paise": sum(i.total_paise for i in rows if i.status == "issued"),
            "credit_available_paise": svc.credit_available(db, current_user.college_id)}


@router.get("/college/billing/invoices/{invoice_id}/pdf")
def my_invoice_pdf(invoice_id: str, current_user: TokenPayload = Depends(COLLEGE), db: Session = Depends(get_db)):
    inv = _invoice(db, invoice_id, current_user.college_id)
    if inv.status == "draft":
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _pdf(inv)
