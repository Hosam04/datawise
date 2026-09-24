import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("config")

# Anchor storage to a fixed, absolute location derived from this file's
# position in the repo (backend/core/config.py -> repo root), instead of the
# process's current working directory. Relying on a relative "storage" path
# breaks as soon as the server is launched from a different working
# directory (a different terminal, an IDE "Run" button, a reload subprocess,
# etc.) -- sessions written by one run become invisible to the next one,
# which is what produces "Dataset not found" errors on chat/status lookups
# even though the session was created successfully.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolve_storage_path(raw_path: str) -> str:
    """Make STORAGE_PATH absolute and stable across process restarts.

    If STORAGE_PATH is already absolute (e.g. set explicitly in the
    environment for deployment), it's used as-is. Otherwise it's resolved
    relative to BASE_DIR (the repo root), never relative to whatever
    directory the process happened to be started from.
    """
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.join(BASE_DIR, raw_path)


def _requier_jwt_secret() -> str:
    """return JWT secret, falling back to a dev-onlydefault with a wrning"""
    secret = os.getenv("JWT_secret_key")
    if secret:
        return secret
    logger.warning(
        "JWT_SECRET_KEY is not set. Using an insecure development default. "
        "Set JWT_SECRET_KEY in the environment before deploying."
    )
    return "dev-only-insecure-jwt-secret-change-me"


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    STORAGE_PATH = _resolve_storage_path(os.getenv("STORAGE_PATH", "storage"))
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 30))