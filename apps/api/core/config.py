import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
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
    
    # Judge0 code execution service URL
    JUDGE0_URL: str = os.getenv("JUDGE0_URL", "http://localhost:2358")
    
    # BigBlueButton / Live class service
    BBB_URL: str = os.getenv("BBB_URL", "http://localhost:8080/bigbluebutton")
    BBB_SECRET: str = os.getenv("BBB_SECRET", "bbb_demo_secret_2026")

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
