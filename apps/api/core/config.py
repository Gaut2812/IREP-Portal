import os
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")
    PROJECT_NAME: str = "IREP Training Portal API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Base URLs
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:3000")
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "irep_super_secret_jwt_key_2026_antigravity")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Multi-tenancy
    DEFAULT_COLLEGE_ID: str = os.getenv("DEFAULT_COLLEGE_ID", "col_demo_001")
    DEFAULT_COLLEGE_NAME: str = "Demo Engineering College"
    
    # Database (absolute path to avoid cwd issues)
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR.as_posix()}/irep.db")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Judge0 code execution service URL & adapter
    JUDGE0_URL: str = os.getenv("JUDGE0_URL", "http://localhost:2358")
    JUDGE0_ADAPTER: str = os.getenv("JUDGE0_ADAPTER", "fake")
    JUDGE0_AUTH_TOKEN: str = os.getenv("JUDGE0_AUTH_TOKEN", "")
    JUDGE0_AUTH_HEADER: str = os.getenv("JUDGE0_AUTH_HEADER", "X-Auth-Token")
    SUBMISSION_RATE_LIMIT_SECONDS: int = int(os.getenv("SUBMISSION_RATE_LIMIT_SECONDS", "5"))
    
    # BigBlueButton / Live class service
    BBB_URL: str = os.getenv("BBB_URL", "http://localhost:8080/bigbluebutton")
    BBB_SECRET: str = os.getenv("BBB_SECRET", "bbb_demo_secret_2026")
    LIVE_CLASS_ADAPTER: str = os.getenv("LIVE_CLASS_ADAPTER", "fake")
    # Microsoft Teams via Graph (LIVE_CLASS_ADAPTER=teams): app-only client credentials.
    # The tenant admin must grant Calendars.ReadWrite, OnlineMeetings.Read.All and
    # OnlineMeetingArtifact.Read.All and set an application access policy (Master Plan).
    GRAPH_TENANT_ID: str = os.getenv("GRAPH_TENANT_ID", "")
    GRAPH_CLIENT_ID: str = os.getenv("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.getenv("GRAPH_CLIENT_SECRET", "")
    GRAPH_BASE_URL: str = os.getenv("GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0")
    GRAPH_LOGIN_URL: str = os.getenv("GRAPH_LOGIN_URL", "https://login.microsoftonline.com")
    TEAMS_DEFAULT_ORGANIZER: str = os.getenv("TEAMS_DEFAULT_ORGANIZER", "")   # used when a trainer has no teams_upn
    TEAMS_REPORT_DELAY_SECONDS: int = int(os.getenv("TEAMS_REPORT_DELAY_SECONDS", "600"))
    LAB_ADAPTER: str = os.getenv("LAB_ADAPTER", "fake")           # fake (dev), docker (dev), jupyterhub (pilot, production)
    JUPYTERHUB_URL: str = os.getenv("JUPYTERHUB_URL", "http://localhost:8001")             # as the API reaches the hub
    JUPYTERHUB_PUBLIC_URL: str = os.getenv("JUPYTERHUB_PUBLIC_URL", "")                    # as students' browsers reach it
    JUPYTERHUB_API_TOKEN: str = os.getenv("JUPYTERHUB_API_TOKEN", "")                      # the hub's "irep-labs" service token
    # Cyber Range (S12): its own hub on its own isolated node (infra/cyber-range); never the shared lab hub
    CYBER_RANGE_HUB_URL: str = os.getenv("CYBER_RANGE_HUB_URL", "")
    CYBER_RANGE_PUBLIC_URL: str = os.getenv("CYBER_RANGE_PUBLIC_URL", "")
    CYBER_RANGE_API_TOKEN: str = os.getenv("CYBER_RANGE_API_TOKEN", "")
    LAB_APPROVAL_DAYS: int = int(os.getenv("LAB_APPROVAL_DAYS", "30"))                      # Cyber Range access lasts this long
    TRANSLATE_ADAPTER: str = os.getenv("TRANSLATE_ADAPTER", "fake")
    # Screen 25 AI Study Buddy. "fake" (dev, deterministic hints) or "anthropic" (Claude API; needs the
    # `anthropic` package and ANTHROPIC_API_KEY). Minors' data: no names or ids are sent; emails and phones are redacted.
    STUDY_BUDDY_ADAPTER: str = os.getenv("STUDY_BUDDY_ADAPTER", "fake")
    STUDY_BUDDY_MODEL: str = os.getenv("STUDY_BUDDY_MODEL", "claude-opus-5-5")
    TRANSLATE_URL: str = os.getenv("TRANSLATE_URL", "http://localhost:5000")
    GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "dev_github_webhook_secret")
    
    # Identity. "local": the API's own JWT (dev default). "keycloak": staff and
    # students sign in through Keycloak; parents keep the API's OTP until the
    # Keycloak SMS OTP (MSG91) lands at pilot. Production requires "keycloak".
    AUTH_PROVIDER: str = os.getenv("AUTH_PROVIDER", "local")
    KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL", "http://localhost:8081")      # as the browser sees it (token issuer)
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "irep")
    KEYCLOAK_AUDIENCE: str = os.getenv("KEYCLOAK_AUDIENCE", "irep-api")

    @property
    def KEYCLOAK_ISSUER(self) -> str:
        return f"{self.KEYCLOAK_URL.rstrip('/')}/realms/{self.KEYCLOAK_REALM}"

    # Outbox dispatch: "thread" drains it inside the API process (dev, no broker);
    # "celery" leaves it to apps/workers (pilot/production); "off" disables both.
    OUTBOX_RUNNER: str = os.getenv(
        "OUTBOX_RUNNER", "celery" if os.getenv("ENVIRONMENT", "development").lower() == "production" else "thread"
    )
    OUTBOX_POLL_SECONDS: float = float(os.getenv("OUTBOX_POLL_SECONDS", "2"))
    OUTBOX_MAX_ATTEMPTS: int = int(os.getenv("OUTBOX_MAX_ATTEMPTS", "5"))
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")  # Valkey speaks the Redis protocol

    # AI Reviewer
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    GEMINI_TIMEOUT_SECONDS: float = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "5.0"))

settings = Settings()
