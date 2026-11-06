"""Health check — public, no secrets in the body."""

from sqlalchemy import text

from ..extensions import db
from . import api_bp


@api_bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        return {"status": "unhealthy"}, 503
    return {"status": "ok", "version": "0.1.0"}, 200
