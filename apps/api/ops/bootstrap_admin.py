"""Create the first SUPER ADMIN on an empty production database and invite it through Keycloak (an
email with a link to set the password; the first sign-in also sets up an authenticator app, 2FA).
Idempotent: a re-run never touches an existing password or authenticator.

    docker compose run --rm api python ops/bootstrap_admin.py --email ops@yourdomain.in --name "IREP Operations"

The super admin then invites IREP staff (Super admin page), signs MoUs and onboards colleges
(Screen 45), and college admins invite
their trainers and students (invites are emailed by Keycloak, see ops/configure_keycloak.py).
--no-email prints the next step instead, for when Keycloak SMTP is not set up yet.
"""
import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.database import SessionLocal
from core.security import PLATFORM_TENANT, get_password_hash
from models.schema import User
from services.keycloak_admin import admin_from_env


def ensure_staff(db, email: str, name: str, role: str = "super_admin") -> User:
    email = email.strip().lower()
    u = db.execute(select(User).filter_by(email=email)).scalar_one_or_none()
    if u is not None:
        if u.college_id != PLATFORM_TENANT or u.role not in ("irep_admin", "super_admin"):
            raise SystemExit(f"{email} already exists with role {u.role!r}; use another email")
        if u.role != role:                                  # promote existing IREP staff (operator action)
            u.role = role
            db.commit()
        return u
    u = User(id=f"usr_irep_{secrets.token_hex(6)}", college_id=PLATFORM_TENANT, email=email, role=role, name=name,
             # Keycloak owns the password in production; this local hash is random and never used
             hashed_password=get_password_hash(secrets.token_urlsafe(32)),
             avatar_initials="".join(p[0] for p in name.split()[:2]).upper() or "IR", language_pref="en")
    db.add(u)
    db.commit()
    return u


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", default="IREP Operations")
    ap.add_argument("--no-email", action="store_true", help="do not send the Keycloak invite email")
    ap.add_argument("--resend-invite", action="store_true",
                    help="send the set-password link again (a plain re-run never touches an existing password or OTP)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        u = ensure_staff(db, args.email, args.name)
        first, _, last = u.name.partition(" ")
        rep = {"username": u.email, "email": u.email, "emailVerified": False, "enabled": True,
               "firstName": first, "lastName": last or "-",
               "attributes": {"irep_user_id": [u.id], "college_id": [u.college_id]}}
    finally:
        db.close()
    kc = admin_from_env()
    existed = kc.find_user(rep["username"]) is not None
    kc.invite(rep, u.role, send_email=not args.no_email, resend=args.resend_invite)
    if existed and not args.resend_invite:
        print(f"{u.email}: already set up; nothing changed (use --resend-invite to email the link again).")
    elif args.no_email:
        print(f"{u.email}: created. In the Keycloak admin console (realm irep > Users), use 'Credentials > Reset password'.")
    else:
        print(f"{u.email}: invite emailed. The link sets the password, then sign in at the portal.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
