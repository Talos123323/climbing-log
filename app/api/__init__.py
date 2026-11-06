"""API blueprint. Submodules register their routes on api_bp;
the factory mounts it at /api.
"""

from flask import Blueprint

api_bp = Blueprint("api", __name__)

# Imported for their side effect (route registration on api_bp).
# Auth / profile / climbs / admin land on the feature branch.
from . import health  # noqa: E402,F401
