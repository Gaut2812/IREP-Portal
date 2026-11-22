"""Point the imported realm "irep" at the real domains and SMTP, and enforce sign-in rules. Idempotent:
re-run after changing APP_DOMAIN or SMTP_* in .env (a re-run changes nothing that is already right).

    docker compose run --rm api python ops/configure_keycloak.py

Keycloak imports infra/keycloak/realm-irep.json (the dev template, no secrets) on first start.
This script then, through the admin REST API inside Docker:
- sets the irep-web client's redirect, web-origin and post-logout URLs to PUBLIC_BASE_URL, and keeps
  it on the browser (PKCE) flow only: no password grant that could skip the OTP step,
- turns self-registration off: accounts are invited or imported, never signed up (docs/PERMISSIONS.md),
- requires HTTPS for every request (sslRequired=all),
- sets the realm's SMTP server from SMTP_* (used for invites, password resets, email verification),
- requires two-factor sign-in (authenticator app, TOTP) for IREP staff and super admins: the realm
  roles irep_admin and super_admin include the marker role irep_2fa, and the "irep browser" flow
  asks everyone with irep_2fa for an OTP code at every sign-in. Someone without an authenticator
  yet is made to set one up before they get in. Other users keep the usual flow (OTP only if they
  chose to set it up).
The SMTP password lives only in .env and in Keycloak's database, never in a file in the repo.
"""
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings
from services.keycloak_admin import admin_from_env

TWO_FA_ROLE = "irep_2fa"
TWO_FA_PARENTS = {"irep_admin": "IREP staff (screens 45-49)", "super_admin": "IREP super admin (above IREP staff)"}
FLOW = "irep browser"
STAFF_SUBFLOW = "irep browser staff OTP"


def realm_changes() -> dict:
    changes = {"sslRequired": "all" if settings.PUBLIC_BASE_URL.startswith("https://") else "external",
               "registrationAllowed": False, "browserFlow": FLOW}
    if settings.SMTP_HOST and settings.SMTP_FROM:
        smtp = {"host": settings.SMTP_HOST, "port": str(settings.SMTP_PORT), "from": settings.SMTP_FROM,
                "fromDisplayName": "IREP Portal", "starttls": str(bool(settings.SMTP_STARTTLS)).lower(), "ssl": "false"}
        if settings.SMTP_USER:
            smtp.update({"auth": "true", "user": settings.SMTP_USER, "password": settings.SMTP_PASSWORD})
        changes["smtpServer"] = smtp
    return changes


def client_changes(client: dict) -> dict:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    attrs = dict(client.get("attributes") or {})
    attrs["post.logout.redirect.uris"] = f"{base}/login"
    attrs["pkce.code.challenge.method"] = "S256"
    return {**client, "redirectUris": [f"{base}/auth/callback"], "webOrigins": [base], "rootUrl": base,
            "attributes": attrs, "standardFlowEnabled": True, "directAccessGrantsEnabled": False,
            "implicitFlowEnabled": False, "serviceAccountsEnabled": False}


# ---- roles ----
def ensure_roles(kc) -> None:
    for name, description in {**TWO_FA_PARENTS, TWO_FA_ROLE: "Marker: two-factor sign-in required"}.items():
        if kc.http.get(f"/roles/{quote(name)}").status_code == 404:
            kc.http.post("/roles", json={"name": name, "description": description}).raise_for_status()
    marker = kc.http.get(f"/roles/{TWO_FA_ROLE}").raise_for_status().json()
    for parent in TWO_FA_PARENTS:
        composites = kc.http.get(f"/roles/{quote(parent)}/composites").raise_for_status().json()
        if not any(c["name"] == TWO_FA_ROLE for c in composites):
            kc.http.post(f"/roles/{quote(parent)}/composites", json=[marker]).raise_for_status()


# ---- browser flow with OTP for staff ----
def _executions(kc, alias: str) -> list:
    return kc.http.get(f"/authentication/flows/{quote(alias, safe='')}/executions").raise_for_status().json()


def _set_requirement(kc, flow_alias: str, execution: dict, requirement: str) -> None:
    if execution.get("requirement") != requirement:
        kc.http.put(f"/authentication/flows/{quote(flow_alias, safe='')}/executions",
                    json={**execution, "requirement": requirement}).raise_for_status()


def _config(kc, execution: dict) -> dict:
    cid = execution.get("authenticationConfig")
    return kc.http.get(f"/authentication/config/{cid}").raise_for_status().json().get("config", {}) if cid else {}


def _role_condition(kc, flow_alias: str, negate: bool, alias: str) -> None:
    """Make sure `flow_alias` holds a REQUIRED "Condition - user role" for irep_2fa (negated or not)."""
    def ours(e):
        return e.get("providerId") == "conditional-user-role" and _config(kc, e).get("condUserRole") == TWO_FA_ROLE \
            and _config(kc, e).get("negate", "false") == str(negate).lower()

    found = next((e for e in _executions(kc, flow_alias) if ours(e)), None)
    if found is None:
        kc.http.post(f"/authentication/flows/{quote(flow_alias, safe='')}/executions/execution",
                     json={"provider": "conditional-user-role"}).raise_for_status()
        found = next(e for e in reversed(_executions(kc, flow_alias))
                     if e.get("providerId") == "conditional-user-role" and not e.get("authenticationConfig"))
        kc.http.post(f"/authentication/executions/{found['id']}/config",
                     json={"alias": alias, "config": {"condUserRole": TWO_FA_ROLE, "negate": str(negate).lower()}}).raise_for_status()
        # conditions first, then the OTP form
        def index(provider_or_id: str) -> int:
            return next((e["index"] for e in _executions(kc, flow_alias)
                         if e["id"] == provider_or_id or e.get("providerId") == provider_or_id), -1)
        while index("auth-otp-form") >= 0 and index(found["id"]) > index("auth-otp-form"):
            kc.http.post(f"/authentication/executions/{found['id']}/raise-priority").raise_for_status()
        found = next(e for e in _executions(kc, flow_alias) if e["id"] == found["id"])
    _set_requirement(kc, flow_alias, found, "REQUIRED")


def ensure_2fa_flow(kc) -> None:
    if not any(f["alias"] == FLOW for f in kc.http.get("/authentication/flows").raise_for_status().json()):
        kc.http.post("/authentication/flows/browser/copy", json={"newName": FLOW}).raise_for_status()
    top = _executions(kc, FLOW)
    forms = next(e for e in top if e.get("authenticationFlow") and e["level"] == 0 and e["displayName"].endswith("forms"))
    optional_otp = next(e for e in top if e.get("authenticationFlow") and "Conditional OTP" in e["displayName"])

    # 1) the stock "OTP if the user set it up" step skips staff (they get step 2, so no double prompt)
    _role_condition(kc, optional_otp["displayName"], negate=True, alias="irep-not-staff")

    # 2) staff: OTP always (the OTP form makes them set up an authenticator if they have none)
    if not any(e["displayName"] == STAFF_SUBFLOW for e in _executions(kc, forms["displayName"])):
        kc.http.post(f"/authentication/flows/{quote(forms['displayName'], safe='')}/executions/flow",
                     json={"alias": STAFF_SUBFLOW, "type": "basic-flow", "provider": "registration-page-form",
                           "description": "Two-factor sign-in for IREP staff and super admins"}).raise_for_status()
    staff = next(e for e in _executions(kc, forms["displayName"]) if e["displayName"] == STAFF_SUBFLOW)
    _set_requirement(kc, forms["displayName"], staff, "CONDITIONAL")
    _role_condition(kc, STAFF_SUBFLOW, negate=False, alias="irep-staff")
    otp = next((e for e in _executions(kc, STAFF_SUBFLOW) if e.get("providerId") == "auth-otp-form"), None)
    if otp is None:
        kc.http.post(f"/authentication/flows/{quote(STAFF_SUBFLOW, safe='')}/executions/execution",
                     json={"provider": "auth-otp-form"}).raise_for_status()
        otp = next(e for e in _executions(kc, STAFF_SUBFLOW) if e.get("providerId") == "auth-otp-form")
    _set_requirement(kc, STAFF_SUBFLOW, otp, "REQUIRED")


def main() -> int:
    kc = admin_from_env()
    ensure_roles(kc)
    ensure_2fa_flow(kc)
    # partial update: only the fields we own; a re-run never rewrites anything else (e.g. a masked SMTP password)
    kc.http.put(f"{kc.base}/admin/realms/{kc.realm}", json=realm_changes()).raise_for_status()
    found = kc.http.get("/clients", params={"clientId": "irep-web"}).raise_for_status().json()
    if not found:
        print("client irep-web not found: was infra/keycloak/realm-irep.json imported?")
        return 1
    kc.http.put(f"/clients/{found[0]['id']}", json=client_changes(found[0])).raise_for_status()
    smtp = "SMTP set" if settings.SMTP_HOST else "no SMTP_HOST: invites and password resets cannot be emailed"
    print(f"realm {kc.realm}: redirects -> {settings.PUBLIC_BASE_URL}; {smtp}; "
          f"self-registration off; two-factor required for {', '.join(TWO_FA_PARENTS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
