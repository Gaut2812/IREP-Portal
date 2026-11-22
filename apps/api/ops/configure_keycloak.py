"""Point the imported realm "irep" at the real domains and the SMTP server. Idempotent; re-run
after changing APP_DOMAIN or SMTP_* in .env.

    docker compose run --rm api python ops/configure_keycloak.py

Keycloak imports infra/keycloak/realm-irep.json (the dev template, no secrets) on first start.
This script then, through the admin REST API inside Docker:
- sets the irep-web client's redirect, web-origin and post-logout URLs to PUBLIC_BASE_URL,
- requires HTTPS for every request (sslRequired=all),
- sets the realm's SMTP server from SMTP_* (used for invites, password resets, email verification).
The SMTP password lives only in .env and in Keycloak's database, never in a file in the repo.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings
from services.keycloak_admin import admin_from_env


def realm_changes() -> dict:
    changes = {"sslRequired": "all" if settings.PUBLIC_BASE_URL.startswith("https://") else "external"}
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
            "attributes": attrs}


def main() -> int:
    kc = admin_from_env()
    # partial update: only the fields we own; a re-run never rewrites anything else (e.g. a masked SMTP password)
    kc.http.put(f"{kc.base}/admin/realms/{kc.realm}", json=realm_changes()).raise_for_status()
    found = kc.http.get("/clients", params={"clientId": "irep-web"}).raise_for_status().json()
    if not found:
        print("client irep-web not found: was infra/keycloak/realm-irep.json imported?")
        return 1
    kc.http.put(f"/clients/{found[0]['id']}", json=client_changes(found[0])).raise_for_status()
    smtp = "SMTP set" if settings.SMTP_HOST else "no SMTP_HOST: invites and password resets cannot be emailed"
    print(f"realm {kc.realm}: redirects -> {settings.PUBLIC_BASE_URL}; {smtp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
