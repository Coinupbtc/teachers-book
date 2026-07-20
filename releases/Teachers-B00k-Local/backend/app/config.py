"""Teachers B00k — Configuration

All config from environment with sensible defaults.
Load once, import everywhere.
"""
import os
import warnings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Placeholder only for local development / tests. Never use as-is in production.
INSECURE_DEFAULT_SECRET = (
    "change-me-in-production-use-64-bytes-here-xxxxxxxxxxxxxxxxxxxxxx"
)


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR}/gradebook.db",
    )
    SECRET_KEY: str = os.getenv("SECRET_KEY", INSECURE_DEFAULT_SECRET)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")
    # When set, every new account must present this private code to register.
    INVITE_CODE: str = os.getenv("TEACHERS_BOOK_INVITE_CODE", "")
    FRONTEND_DIR: Path = BASE_DIR / "frontend"
    # development | production — production refuses the placeholder SECRET_KEY
    ENV: str = os.getenv("TEACHERS_BOOK_ENV", "development").lower()

    def validate(self) -> None:
        """Refuse insecure defaults when running as production."""
        env = self.ENV
        if env in ("production", "prod"):
            if self.SECRET_KEY == INSECURE_DEFAULT_SECRET:
                raise RuntimeError(
                    "SECRET_KEY must be set to a strong random value when "
                    "TEACHERS_BOOK_ENV=production (do not use the placeholder)."
                )
            if "*" in self.CORS_ORIGINS and not os.getenv(
                "TEACHERS_BOOK_ALLOW_OPEN_CORS"
            ):
                raise RuntimeError(
                    "CORS_ORIGINS must not be '*' in production "
                    "(or set TEACHERS_BOOK_ALLOW_OPEN_CORS=1 to override)."
                )
        elif self.SECRET_KEY == INSECURE_DEFAULT_SECRET:
            warnings.warn(
                "Using default SECRET_KEY — fine for local dev only. "
                "Set SECRET_KEY and TEACHERS_BOOK_ENV=production for any shared deploy.",
                stacklevel=2,
            )


settings = Settings()
settings.validate()
