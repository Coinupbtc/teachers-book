"""Teachers B00k — Configuration

All config from environment with sensible defaults.
Load once, import everywhere.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR}/gradebook.db"
    )
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "change-me-in-production-use-64-bytes-here-xxxxxxxxxxxxxxxxxxxxxx"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    # When set, every new account must present this private code to register.
    INVITE_CODE: str = os.getenv("TEACHERS_BOOK_INVITE_CODE", "")
    FRONTEND_DIR: Path = BASE_DIR / "frontend"

settings = Settings()
