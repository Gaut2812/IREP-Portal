"""Keycloak admin REST client (realm "irep"): user sync and invites.

Env: KEYCLOAK_ADMIN_URL (default http://localhost:8081), KEYCLOAK_ADMIN_USER,
KEYCLOAK_ADMIN_PASSWORD (dev defaults admin/admin; use a service account in
the pilot), KEYCLOAK_REALM.
"""
import os

import httpx

from core.keycloak import IREP_ROLES

# Keycloak enforces OTP for these at every sign-in (ops/configure_keycloak.py flow)
TWO_FACTOR_ROLES = ("irep_admin", "super_admin")


class _AdminToken(httpx.Auth):
    """Master-realm admin token; fetched again on a 401 (admin-cli tokens live 60 s, a long sync outlives them).
    The password is only sent to the token endpoint and never logged."""

    def __init__(self, base: str, user: str, password: str, transport=None):
        self._transport = transport
        self._url, self._form = f"{base}/realms/master/protocol/openid-connect/token",             {"grant_type": "password", "client_id": "admin-cli", "username": user, "password": password}
        self._token = None

    def _fetch(self) -> str:
        with httpx.Client(transport=self._transport, timeout=10) as c:
            r = c.post(self._url, data=self._form)
        if r.status_code != 200:
            raise RuntimeError(f"Keycloak admin sign-in failed ({r.status_code}): check KEYCLOAK_ADMIN_USER / KEYCLOAK_ADMIN_PASSWORD")
        return r.json()["access_token"]

    def auth_flow(self, request):
        if self._token is None:
            self._token = self._fetch()
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        if response.status_code == 401:
            self._token = self._fetch()
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


class KeycloakAdmin:
    def __init__(self, base: str, realm: str, user: str, password: str, transport=None):
        self.base, self.realm = base.rstrip("/"), realm
        auth = _AdminToken(self.base, user, password, transport)
        auth._token = auth._fetch()                       # fail fast on wrong credentials
        self.http = httpx.Client(base_url=f"{self.base}/admin/realms/{realm}", timeout=10, auth=auth, transport=transport)

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

    def invite(self, rep: dict, role: str, send_email: bool, resend: bool = False) -> str:
        """New user: 'update password' + 'verify email' (+ 'configure OTP' for IREP staff roles) required
        actions, no password set by us, and optionally the email with the link.

        Idempotent (outbox retries, re-run scripts): an existing user keeps their password, verified
        email and OTP; only names, tenancy attributes and the role are re-synced. resend=True sends the
        link again (and re-adds the required actions) on purpose."""
        actions = ["UPDATE_PASSWORD", "VERIFY_EMAIL"] + (["CONFIGURE_TOTP"] if role in TWO_FACTOR_ROLES else [])
        existing = self.find_user(rep["username"])
        if existing and not resend:
            keep = {k: v for k, v in rep.items() if k not in ("emailVerified", "requiredActions", "enabled")}
            kc_id = self.upsert_user(keep)
            self.set_only_irep_role(kc_id, role)
            return kc_id
        kc_id = self.upsert_user({**rep, "requiredActions": actions})
        self.set_only_irep_role(kc_id, role)
        if send_email:
            self.http.put(f"/users/{kc_id}/execute-actions-email", json=actions).raise_for_status()
        return kc_id


def admin_from_env() -> KeycloakAdmin:
    return KeycloakAdmin(os.getenv("KEYCLOAK_ADMIN_URL", "http://localhost:8081"), os.getenv("KEYCLOAK_REALM", "irep"),
                         os.getenv("KEYCLOAK_ADMIN_USER", "admin"), os.getenv("KEYCLOAK_ADMIN_PASSWORD", "admin"))
