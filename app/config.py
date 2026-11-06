"""Application configuration.

One name for the JWT secret everywhere: JWT_SECRET. It appears in exactly
two places — here and .env.example. There is no Flask SECRET_KEY in v1
because the API is bearer-token-only (no sessions, no flash messages).

Production env vars are read ONLY inside production_overrides(), which is
only called when the production config is actually selected. Nothing in
this module raises at import time.
"""

import os
from datetime import timedelta

from sqlalchemy.pool import StaticPool


class BaseConfig:
    """Shared settings. JWT_TTL is a timedelta; routes return it as seconds."""

    JWT_TTL = timedelta(hours=int(os.environ.get("JWT_TTL_HOURS", "12")))
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///dev.db"


class TestingConfig(BaseConfig):
    TESTING = True
    JWT_SECRET = "testing-only"
    # In-memory SQLite shared across threads via StaticPool, so the
    # test_client and the app see the same database.
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,
        "connect_args": {"check_same_thread": False},
    }


class ProductionConfig(BaseConfig):
    DEBUG = False
    # Deliberately None here — filled in by production_overrides() only
    # when production is selected. A missing env var must crash startup
    # loudly instead of silently falling back to a public dev secret.
    JWT_SECRET = None
    SQLALCHEMY_DATABASE_URI = None


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

REQUIRED_IN_PRODUCTION = ("JWT_SECRET", "DATABASE_URL")


def production_overrides() -> dict:
    """Read production-only env vars, failing fast if any are missing.

    Called only from create_app() when config_name == "production".
    Never called at import time, so `flask db` / tests / dev never
    trip over missing production variables.
    """
    missing = [k for k in REQUIRED_IN_PRODUCTION if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "refusing to start in production; missing env vars: "
            + ", ".join(missing)
        )
    return {
        "JWT_SECRET": os.environ["JWT_SECRET"],
        "SQLALCHEMY_DATABASE_URI": os.environ["DATABASE_URL"],
    }
