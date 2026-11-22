"""Outbound email and SMS for the pilot (NOTIFY_ADAPTER=live).

- Email: plain SMTP with STARTTLS (any provider; Brevo's free tier works for a pilot).
- SMS: Fast2SMS (bulkV2, SMS_PROVIDER=fast2sms) or MSG91 (flow API with DLT-approved templates,
  SMS_PROVIDER=msg91). It is a switch, OFF by default (SMS_PROVIDER=off): while it is off, anything meant for SMS goes to the user's email instead,
  so parents still hear about leave decisions, events and support plans at no cost.

Gateway errors raise, so the outbox retries the delivery (architecture rule 3). The parent
sign-in OTP is the one direct send (routers/auth.py), because an outbox row would hold the code.
"""
import smtplib
from email.message import EmailMessage
from typing import Optional

import httpx

from core.config import settings


class GatewayError(RuntimeError):
    pass


def send_email(to: str, subject: str, body: str, smtp_factory=smtplib.SMTP) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        raise GatewayError("SMTP is not configured (SMTP_HOST, SMTP_FROM)")
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.SMTP_FROM, to, subject
    msg.set_content(body or subject)
    with smtp_factory(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_STARTTLS:
            smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(msg)


def _indian_mobile(phone: str) -> str:
    digits = "".join(ch for ch in phone or "" if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) != 12 or not digits.startswith("91"):
        raise GatewayError("Not an Indian mobile number")
    return digits


def send_sms(phone: str, template_id: str, variables: dict, client: Optional[httpx.Client] = None) -> None:
    """MSG91 flow API: one recipient, template variables as top-level keys."""
    if not settings.MSG91_AUTH_KEY or not template_id:
        raise GatewayError("MSG91 is not configured (MSG91_AUTH_KEY and a template id)")
    http = client or httpx.Client(timeout=20)
    r = http.post(settings.MSG91_URL, headers={"authkey": settings.MSG91_AUTH_KEY, "content-type": "application/json"},
                  json={"template_id": template_id, "short_url": "0", "recipients": [{"mobiles": _indian_mobile(phone), **variables}]})
    if r.status_code >= 400:
        raise GatewayError(f"MSG91 returned {r.status_code}")
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if str(data.get("type", "success")).lower() == "error":
        raise GatewayError(f"MSG91 error: {data.get('message')}")


def send_fast2sms(phone: str, *, message: Optional[str] = None, otp: Optional[str] = None,
                  client: Optional[httpx.Client] = None) -> None:
    """Fast2SMS bulkV2 POST, key in the "authorization" header (never in the URL, so it stays out of
    proxy and access logs). route q sends `message`; route otp sends only the code (variables_values)."""
    if not settings.FAST2SMS_API_KEY:
        raise GatewayError("Fast2SMS is not configured (FAST2SMS_API_KEY)")
    number = _indian_mobile(phone)[2:]                  # Fast2SMS takes the 10-digit number
    if otp is not None and settings.FAST2SMS_OTP_ROUTE.lower() == "otp":
        body = {"route": "otp", "variables_values": otp, "numbers": number}
    else:
        body = {"route": settings.FAST2SMS_ROUTE or "q", "message": message or "", "language": "english",
                "flash": 0, "numbers": number}
    http = client or httpx.Client(timeout=20)
    r = http.post(settings.FAST2SMS_URL, json=body,
                  headers={"authorization": settings.FAST2SMS_API_KEY, "content-type": "application/json",
                           "cache-control": "no-cache"})
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400 or data.get("return") is not True:
        # the reply never contains the key; keep only Fast2SMS's own message
        raise GatewayError(f"Fast2SMS returned {r.status_code}: {str(data.get('message'))[:120]}")


def _sms(phone: str, text: str, otp: Optional[str] = None) -> None:
    provider = settings.SMS_PROVIDER.lower()
    if provider == "fast2sms":
        send_fast2sms(phone, message=text, otp=otp)
    elif otp is not None:
        send_sms(phone, settings.MSG91_OTP_TEMPLATE_ID, {"otp": otp})
    else:
        send_sms(phone, settings.MSG91_TEMPLATE_ID, {"message": text[:300]})


def real_email(email: Optional[str]) -> bool:
    """Placeholder addresses (import without a parent email: <mobile>@parents.invalid) are not mailboxes."""
    return bool(email) and "@" in email and not email.lower().endswith(".invalid")


def sms_on() -> bool:
    return settings.SMS_PROVIDER.lower() in ("fast2sms", "msg91")


def deliver(user, channel: str, title: str, body: Optional[str]) -> str:
    """One notification. Returns the delivery status stored on the notification row."""
    text = f"{title}\n\n{body}" if body else title
    if channel == "sms" and sms_on():
        if not user.phone:
            return "skipped:no_phone"
        _sms(user.phone, text[:300])
        return "delivered"
    if channel in ("email", "sms"):                     # SMS switched off: email instead
        if not real_email(user.email):
            return "skipped:no_email"
        send_email(user.email, title, f"{text}\n\n{settings.PUBLIC_BASE_URL}")
        return "delivered" if channel == "email" else "delivered:email"
    return "skipped:unsupported_channel"


def send_parent_otp(user, otp: str, minutes: int) -> str:
    """The sign-in code, by PARENT_OTP_CHANNEL (email by default; sms needs SMS_PROVIDER fast2sms or msg91)."""
    if settings.PARENT_OTP_CHANNEL.lower() == "sms" and sms_on():
        _sms(user.phone, f"{otp} is your IREP sign-in code. Valid for {minutes} minutes. Do not share it.", otp=otp)
        return "sms"
    if not real_email(user.email):
        return "skipped:no_email"          # same answer to the caller (no account probing); audit shows it
    send_email(user.email, "Your IREP sign-in code",
               f"Your IREP sign-in code is {otp}. It is valid for {minutes} minutes.\n"
               f"If you did not ask for it, you can ignore this email.\n\n"
               f"உங்கள் IREP உள்நுழைவுக் குறியீடு {otp}. இது {minutes} நிமிடங்களுக்கு மட்டுமே செல்லும்.")
    return "email"


def mask_email(email: str) -> str:
    local, _, domain = (email or "").partition("@")
    return f"{local[:1]}***@{domain}" if local and domain else ""
