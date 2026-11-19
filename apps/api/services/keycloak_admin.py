"""Keycloak admin REST client (realm "irep"): user sync and invites.

Env: KEYCLOAK_ADMIN_URL (default http://localhost:8081), KEYCLOAK_ADMIN_USER,
KEYCLOAK_ADMIN_PASSWORD (dev defaults admin/admin; use a service account in
the pilot), KEYCLOAK_REALM.
"""
import os

import httpx

from core.keycloak import IREP_ROLES


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

    def invite(self, rep: dict, role: str, send_email: bool) -> str:
        """Create the user with 'update password' + 'verify email' required
        actions (no password set by us) and optionally email the link."""
        kc_id = self.upsert_user({**rep, "requiredActions": ["UPDATE_PASSWORD", "VERIFY_EMAIL"]})
        self.set_only_irep_role(kc_id, role)
        if send_email:
            self.http.put(f"/users/{kc_id}/execute-actions-email",
                          json=["UPDATE_PASSWORD", "VERIFY_EMAIL"]).raise_for_status()
        return kc_id


def admin_from_env() -> KeycloakAdmin:
    return KeycloakAdmin(os.getenv("KEYCLOAK_ADMIN_URL", "http://localhost:8081"), os.getenv("KEYCLOAK_REALM", "irep"),
                         os.getenv("KEYCLOAK_ADMIN_USER", "admin"), os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"))
