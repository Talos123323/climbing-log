"""Admin-only routes.

401 = no/bad token. 403 = valid token, role is not "admin".
The role is read from the database user loaded by token_required —
never from the JWT payload — so demoting a user takes effect on
their next request, not when their token expires.
"""

from ..extensions import db
from ..models.user import User
from . import api_bp
from .helpers import require_admin, serialize_user


@api_bp.get("/admin/users")
@require_admin
def list_users():
    users = db.session.execute(db.select(User).order_by(User.id)).scalars().all()
    # Explicit field list via serialize_user — password_hash is never
    # in an admin payload either.
    return [serialize_user(u) for u in users], 200
