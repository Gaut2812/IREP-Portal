"""Start-up checks for ENVIRONMENT=production (architecture rule 10: production refuses fakes).

`problems(settings)` returns every misconfiguration at once so an operator can fix them in one
pass; main.py refuses to start when the list is not empty.

Pilot exception: ALLOW_DEMO_ADAPTERS may name features that are not part of the pilot and keep
their demo adapter (judge0 for the Coding Lab, labs for Virtual Labs, study_buddy for the AI
Study Buddy, live_classes for the in-portal classroom until Teams is consented). Everything that real users rely on (sign-in, email, Teams, the database) stays strict.
"""
from typing import List

DEMO_FEATURES = {"judge0", "labs", "study_buddy", "live_classes"}
DEFAULT_JWT_SECRET = "irep_super_secret_jwt_key_2026_antigravity"


def allowed_demo(settings) -> set:
    return {x.strip().lower() for x in (settings.ALLOW_DEMO_ADAPTERS or "").split(",") if x.strip()}


def problems(settings) -> List[str]:
    out: List[str] = []
    demo = allowed_demo(settings)
    unknown = demo - DEMO_FEATURES
    if unknown:
        out.append(f"ALLOW_DEMO_ADAPTERS has unknown names: {', '.join(sorted(unknown))} (allowed: judge0, labs, study_buddy, live_classes).")

    # identity and secrets
    if settings.AUTH_PROVIDER.lower() != "keycloak":
        out.append("AUTH_PROVIDER must be keycloak.")
    if settings.JWT_SECRET_KEY == DEFAULT_JWT_SECRET or len(settings.JWT_SECRET_KEY) < 32:
        out.append("JWT_SECRET_KEY must be a new random value of at least 32 characters (openssl rand -hex 32).")
    if not settings.PUBLIC_BASE_URL.startswith("https://"):
        out.append("PUBLIC_BASE_URL must be the https address of the portal.")
    if not settings.KEYCLOAK_URL.startswith("https://"):
        out.append("KEYCLOAK_URL must be the https address of Keycloak as browsers see it.")
    if not settings.DATABASE_URL.startswith(("postgresql", "postgres")):
        out.append("DATABASE_URL must point to PostgreSQL.")

    # engines outside the pilot may stay on their demo adapter when named in ALLOW_DEMO_ADAPTERS
    if "judge0" not in demo and (settings.JUDGE0_ADAPTER != "judge0" or not settings.JUDGE0_URL or not settings.JUDGE0_AUTH_TOKEN):
        out.append("JUDGE0_ADAPTER must be judge0 with JUDGE0_URL and JUDGE0_AUTH_TOKEN (or add judge0 to ALLOW_DEMO_ADAPTERS).")
    if "labs" not in demo and (settings.LAB_ADAPTER.lower() != "jupyterhub" or not settings.JUPYTERHUB_URL or not settings.JUPYTERHUB_API_TOKEN):
        out.append("LAB_ADAPTER must be jupyterhub with JUPYTERHUB_URL and JUPYTERHUB_API_TOKEN (or add labs to ALLOW_DEMO_ADAPTERS).")
    if "study_buddy" not in demo and settings.STUDY_BUDDY_ADAPTER.lower() != "anthropic":
        out.append("STUDY_BUDDY_ADAPTER must be anthropic (or add study_buddy to ALLOW_DEMO_ADAPTERS).")

    if settings.GITHUB_WEBHOOK_SECRET in ("", "dev_github_webhook_secret"):
        out.append("GITHUB_WEBHOOK_SECRET must be a new random value (openssl rand -hex 32).")

    # live classes
    live = settings.LIVE_CLASS_ADAPTER.lower()
    if live not in ("teams", "bbb") and "live_classes" not in demo:
        out.append("LIVE_CLASS_ADAPTER must be teams (or bbb). Until Teams is set up, add live_classes to "
                   "ALLOW_DEMO_ADAPTERS to keep the in-portal classroom without video.")
    if live == "bbb" and settings.BBB_SECRET in ("", "bbb_demo_secret_2026"):
        out.append("LIVE_CLASS_ADAPTER=bbb needs the real BBB_URL and BBB_SECRET.")
    if live == "teams" and not (settings.GRAPH_TENANT_ID and settings.GRAPH_CLIENT_ID and settings.GRAPH_CLIENT_SECRET):
        out.append("LIVE_CLASS_ADAPTER=teams needs GRAPH_TENANT_ID, GRAPH_CLIENT_ID and GRAPH_CLIENT_SECRET (docs/deploy/TEAMS_SETUP.md).")

    # email (always) and SMS (only when switched on)
    if settings.NOTIFY_ADAPTER.lower() != "live":
        out.append("NOTIFY_ADAPTER must be live, so email (and SMS when on) is really sent.")
    if not (settings.SMTP_HOST and settings.SMTP_FROM):
        out.append("SMTP_HOST and SMTP_FROM are required: parent sign-in codes and notices go by email.")
    sms = settings.SMS_PROVIDER.lower()
    if sms not in ("off", "fast2sms", "msg91"):
        out.append("SMS_PROVIDER must be off, fast2sms or msg91.")
    if sms == "fast2sms" and not settings.FAST2SMS_API_KEY:
        out.append("SMS_PROVIDER=fast2sms needs FAST2SMS_API_KEY (Fast2SMS dashboard > Dev API).")
    if sms == "msg91" and not (settings.MSG91_AUTH_KEY and settings.MSG91_TEMPLATE_ID and settings.MSG91_OTP_TEMPLATE_ID):
        out.append("SMS_PROVIDER=msg91 needs MSG91_AUTH_KEY, MSG91_TEMPLATE_ID and MSG91_OTP_TEMPLATE_ID (DLT-approved templates).")
    if settings.PARENT_OTP_CHANNEL.lower() not in ("email", "sms"):
        out.append("PARENT_OTP_CHANNEL must be email or sms.")
    if settings.PARENT_OTP_CHANNEL.lower() == "sms" and sms not in ("fast2sms", "msg91"):
        out.append("PARENT_OTP_CHANNEL=sms needs SMS_PROVIDER=fast2sms or msg91.")

    if settings.AV_ADAPTER.lower() != "clamd":
        out.append("AV_ADAPTER must be clamd: every upload is virus-scanned by ClamAV before it is saved.")

    # files and background work
    if settings.STORAGE_ADAPTER.lower() != "local":
        out.append("STORAGE_ADAPTER must be local for now (the S3 adapter is an interface only, see services/storage.py).")
    if settings.OUTBOX_RUNNER != "celery":
        out.append("OUTBOX_RUNNER must be celery (the worker container drains the outbox).")
    return out
