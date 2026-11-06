"""Shared helpers: error envelope, JWT minting, auth decorators,
serializers, and validators.

Every error response in the API uses one envelope:
    {"error": "<Short Type>", "message": "...", "details": {...optional}}
No HTML errors, and no password / password_hash in any response.
"""

import re
from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from ..extensions import db
from ..models.climb import OUTCOMES
from ..models.user import User

# ---------------------------------------------------------------- errors


def error(message, status, error_type, details=None):
    """Build the standard error envelope."""
    body = {"error": error_type, "message": message}
    if details is not None:
        body["details"] = details
    return jsonify(body), status


def bad_request(message="Request validation failed", details=None):
    return error(message, 400, "Bad Request", details)


def unauthorized(message="Authentication required"):
    return error(message, 401, "Unauthorized")


def not_found(message="Climb not found"):
    return error(message, 404, "Not Found")


def get_json_body():
    """Return (data, error_response). Non-JSON / non-object bodies are 400."""
    if not request.is_json:
        return None, bad_request(details={"body": "expected a JSON object"})
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, bad_request(details={"body": "expected a JSON object"})
    return data, None


# ---------------------------------------------------------------- tokens


def mint_token(user):
    """Mint a JWT for a user. Payload is minimal: sub, iat, exp only.

    The role is NOT in the token — require_admin reads it fresh from the
    database, so demoting a user takes effect on their next request,
    not when their token expires.
    """
    ttl = current_app.config["JWT_TTL"]  # a timedelta
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")
    return token, int(ttl.total_seconds())


def token_required(f):
    """Decorator: require a valid Bearer token, load the user from the DB.

    Missing / malformed / expired token -> 401. Valid token whose user
    row is gone -> 401 as well (the credentials are effectively invalid).
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return unauthorized()
        token = auth[len("Bearer "):].strip()
        if not token:
            return unauthorized()
        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError:
            return unauthorized("Token has expired")
        except jwt.InvalidTokenError:
            return unauthorized("Invalid token")
        user = db.session.get(User, payload.get("sub"))
        if user is None:
            return unauthorized()
        g.current_user = user
        return f(*args, **kwargs)

    return wrapper


def require_admin(f):
    """Decorator: token check first, then role check from the DB user.

    401 = no/bad token (from token_required). 403 = valid token, role
    is not "admin". The two are never merged — clients retry them
    differently, and merging them would hide which check failed.
    """

    @wraps(f)
    @token_required
    def wrapper(*args, **kwargs):
        if g.current_user.role != "admin":
            return error("Admin privileges required", 403, "Forbidden")
        return f(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------- serializers


def _iso(value):
    return value.isoformat() if value is not None else None


def serialize_user(user):
    """Public user shape. Explicit field list — never serialize the ORM
    object wholesale, or a new column (e.g. password_hash) leaks."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "created_at": _iso(user.created_at),
    }


def serialize_climb(climb):
    # user_id is the column name; owner_id is the same value under the
    # name the lesson notes used, so both readings of the design agree.
    return {
        "id": climb.id,
        "route_name": climb.route_name,
        "grade": climb.grade,
        "outcome": climb.outcome,
        "climbing_type": climb.climbing_type,
        "location": climb.location,
        "climbed_at": _iso(climb.climbed_at),
        "notes": climb.notes,
        "user_id": climb.user_id,
        "owner_id": climb.user_id,
        "created_at": _iso(climb.created_at),
        "updated_at": _iso(climb.updated_at),
    }


# ---------------------------------------------------------------- validators

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Fields the client may never set on a climb — the server owns them.
# They are ignored/overwritten, not rejected: clients round-trip fetched
# objects, and silently echoing them back would be a lie either way.
# (Profile is the opposite: email/password there are rejected, because
# a client sending them has real intent to change them.)
IGNORED_CLIMB_FIELDS = {"id", "owner_id", "user_id", "created_at", "updated_at"}


def _parse_climbed_at(value, details):
    if value is None:
        return None
    if not isinstance(value, str):
        details["climbed_at"] = "must be an ISO 8601 datetime string"
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        details["climbed_at"] = "must be an ISO 8601 datetime string"
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _optional_str(data, field, details, max_len=None):
    value = data.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        details[field] = "must be a string"
        return None
    if max_len is not None and len(value) > max_len:
        details[field] = f"must be at most {max_len} characters"
        return None
    return value


def validate_climb(data):
    """The ONE climb validator, shared by POST and PUT.

    Returns (cleaned_dict, details_dict). details is non-empty on failure.
    Full replacement: route_name and outcome are required on both
    POST and PUT; optional fields absent from the body become None.
    """
    details = {}

    route_name = data.get("route_name")
    if not isinstance(route_name, str) or not route_name.strip():
        details["route_name"] = "route_name is required"

    outcome = data.get("outcome")
    if outcome not in OUTCOMES:
        details["outcome"] = "must be one of: " + ", ".join(OUTCOMES)

    grade = _optional_str(data, "grade", details, max_len=32)
    climbing_type = _optional_str(data, "climbing_type", details, max_len=32)
    location = _optional_str(data, "location", details, max_len=255)
    notes = _optional_str(data, "notes", details)
    climbed_at = _parse_climbed_at(data.get("climbed_at"), details)

    if details:
        return None, details
    return {
        "route_name": route_name.strip(),
        "grade": grade,
        "outcome": outcome,
        "climbing_type": climbing_type,
        "location": location,
        "climbed_at": climbed_at,
        "notes": notes,
    }, {}


def validate_email_password(data):
    """Shared email/password validation for register and login shape."""
    details = {}
    email = data.get("email")
    if not isinstance(email, str) or not _EMAIL_RE.match(email):
        details["email"] = "must be a valid email address"
    password = data.get("password")
    if not isinstance(password, str) or len(password) < 8:
        details["password"] = "must be at least 8 characters"
    if details:
        return None, details
    return {"email": email, "password": password}, {}


def parse_pagination():
    """Parse ?page=&per_page= — defaults page=1, per_page=20, max 50.

    Returns (page, per_page, error_response). Invalid values are 400
    with field-level details, never a silent clamp.
    """
    raw_page = request.args.get("page", "1")
    raw_per_page = request.args.get("per_page", "20")
    details = {}
    try:
        page = int(raw_page)
        if page < 1:
            details["page"] = "Must be at least 1"
    except (TypeError, ValueError):
        details["page"] = "Must be an integer"
        page = None
    try:
        per_page = int(raw_per_page)
        if per_page < 1:
            details["per_page"] = "Must be at least 1"
        elif per_page > 50:
            details["per_page"] = "Must be at most 50"
    except (TypeError, ValueError):
        details["per_page"] = "Must be an integer"
        per_page = None
    if details:
        return None, None, bad_request(
            message="Invalid pagination parameters", details=details
        )
    return page, per_page, None


def parse_int_id(raw_id):
    """Route <id> must be an integer — /api/climbs/abc is 400, not 404."""
    try:
        return int(raw_id), None
    except (TypeError, ValueError):
        return None, bad_request(details={"id": "Must be an integer"})
