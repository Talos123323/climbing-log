"""API blueprint. Submodules register their routes on api_bp;
the factory mounts it at /api.
"""

from flask import Blueprint

api_bp = Blueprint("api", __name__)

# Imported for their side effect (route registration on api_bp).
from . import admin, auth, climbs, health, profile  # noqa: E402,F401
