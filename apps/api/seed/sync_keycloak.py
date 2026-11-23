"""Create or update portal users in Keycloak (realm "irep"). Idempotent.

    python seed/sync_keycloak.py                 # the named demo accounts
    python seed/sync_keycloak.py --all           # every non-parent user in the DB
    python seed/sync_keycloak.py --email x@y     # one user

Each Keycloak user gets: username/email, first/last name, the realm role, and
the admin-only attributes irep_user_id (users.id) and college_id that the API
reads from the token. Parents are skipped: they sign in with the API's OTP
(email by default, MSG91 SMS as a switch; docs/deploy/DEPLOY.md).

DEMO ONLY: --password sets the same password on every synced account
(default: DEMO_PASSWORD or password123). Never run with --password against
real users; the pilot uses Keycloak's own reset/verify-email flows.

Env: KEYCLOAK_ADMIN_URL (default http://localhost:8081), KEYCLOAK_ADMIN_USER,
KEYCLOAK_ADMIN_PASSWORD (dev defaults admin/admin), KEYCLOAK_REALM.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.database import SessionLocal
from core.keycloak import IREP_ROLES
from services.keycloak_admin import KeycloakAdmin, admin_from_env
from models.schema import User

DEMO_EMAILS = ["priya.r@demo.edu", "arun.k@demo.edu", "admin@demo.edu", "staff@irep.demo", "super@irep.demo"]


def representation(u: User) -> dict:
    first, _, last = (u.name or u.email).partition(" ")
    return {
        "username": u.email.lower(), "email": u.email.lower(), "emailVerified": True, "enabled": bool(u.is_active),
        "firstName": first, "lastName": last or "-",
        "attributes": {"irep_user_id": [u.id], "college_id": [u.college_id]},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true")
    g.add_argument("--email", action="append")
    ap.add_argument("--password", default=os.getenv("DEMO_PASSWORD", "password123"))
    args = ap.parse_args()
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        # it sets one shared password on every account it touches
        print("sync_keycloak.py is for demo data only and refuses to run with ENVIRONMENT=production. "
              "Real accounts are invited (ops/bootstrap_admin.py, college onboarding, student import).")
        return 2

    kc = admin_from_env()
    db = SessionLocal()
    try:
        q = select(User).where(User.role != "parent")
        if not args.all:
            q = q.where(User.email.in_([e.lower() for e in (args.email or DEMO_EMAILS)]))
        users = db.execute(q.order_by(User.email)).scalars().all()
    finally:
        db.close()

    for u in users:
        if u.role not in IREP_ROLES:
            print(f"skip {u.email}: role {u.role!r} is not an IREP realm role")
            continue
        kc_id = kc.upsert_user(representation(u))
        kc.set_password(kc_id, args.password)
        kc.set_only_irep_role(kc_id, u.role)
    print(f"synced {len(users)} user(s) to realm {kc.realm}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
