import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _database_url() -> str:
    value = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://datapilot:datapilot@localhost:5432/datapilot",
    )
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix):]
    return value


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", PROJECT_ROOT / "uploads"))
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

    OUTBOX_FOLDER = Path(os.environ.get("OUTBOX_FOLDER", PROJECT_ROOT / "outbox"))
    ENABLE_SCHEDULER = os.environ.get("ENABLE_SCHEDULER", "1") == "1"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_flag(
        "SESSION_COOKIE_SECURE", os.environ.get("FLASK_DEBUG") != "1"
    )

    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1") == "1"
