"""Create or update portal users in Keycloak (realm "irep"). Idempotent.

    python seed/sync_keycloak.py                 # the named demo accounts
    python seed/sync_keycloak.py --all           # every non-parent user in the DB
    python seed/sync_keycloak.py --email x@y     # one user

Each Keycloak user gets: username/email, first/last name, the realm role, and
the admin-only attributes irep_user_id (users.id) and college_id that the API
reads from the token. Parents are skipped: they sign in with the API's OTP
until Keycloak has SMS OTP (MSG91, pilot).

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

import httpx
from sqlalchemy import select

from core.database import SessionLocal
from core.keycloak import IREP_ROLES
from models.schema import User

DEMO_EMAILS = ["priya.r@demo.edu", "arun.k@demo.edu", "admin@demo.edu"]


class KeycloakAdmin:
    def __init__(self, base: str, realm: str, user: str, password: str):
        self.base, self.realm = base.rstrip("/"), realm
        tok = httpx.post(f"{self.base}/realms/master/protocol/openid-connect/token",
                         data={"grant_type": "password", "client_id": "admin-cli", "username": user, "password": password},
                         timeout=10)
        tok.raise_for_status()
        self.http = httpx.Client(base_url=f"{self.base}/admin/realms/{realm}", timeout=10,
                                 headers={"Authorization": f"Bearer {tok.json()['access_token']}"})

    def find_user(self, username: str):
        r = self.http.get("/users", params={"username": username, "exact": "true"})
        r.raise_for_status()
        return r.json()[0] if r.json() else None

    def upsert_user(self, rep: dict) -> str:
        existing = self.find_user(rep["username"])
        if existing:
            self.http.put(f"/users/{existing['id']}", json={**existing, **rep}).raise_for_status()
            return existing["id"]
        r = self.http.post("/users", json=rep)
        r.raise_for_status()
        return r.headers["Location"].rsplit("/", 1)[-1]

    def set_password(self, kc_id: str, password: str) -> None:
        self.http.put(f"/users/{kc_id}/reset-password",
                      json={"type": "password", "value": password, "temporary": False}).raise_for_status()

    def set_only_irep_role(self, kc_id: str, role: str) -> None:
        current = self.http.get(f"/users/{kc_id}/role-mappings/realm").raise_for_status().json()
        stale = [r for r in current if r["name"] in IREP_ROLES and r["name"] != role]
        if stale:
            self.http.request("DELETE", f"/users/{kc_id}/role-mappings/realm", json=stale).raise_for_status()
        if not any(r["name"] == role for r in current):
            rep = self.http.get(f"/roles/{role}").raise_for_status().json()
            self.http.post(f"/users/{kc_id}/role-mappings/realm", json=[rep]).raise_for_status()


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

    kc = KeycloakAdmin(os.getenv("KEYCLOAK_ADMIN_URL", "http://localhost:8081"), os.getenv("KEYCLOAK_REALM", "irep"),
                       os.getenv("KEYCLOAK_ADMIN_USER", "admin"), os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"))
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
