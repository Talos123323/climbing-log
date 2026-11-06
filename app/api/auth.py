"""Auth: register and login. Both are public — login is the endpoint
that mints the token, so requiring one there would be circular.
"""

import bcrypt
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.user import User
from . import api_bp
from .helpers import (
    bad_request,
    error,
    get_json_body,
    mint_token,
    serialize_user,
    validate_email_password,
)

# Precomputed bcrypt hash of a fixed string. Used for the dummy compare
# when the email is not found, so a wrong-email login costs the same
# time as a wrong-password login and reveals nothing about registration.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password-for-timing", bcrypt.gensalt())


@api_bp.post("/auth/register")
def register():
    data, err = get_json_body()
    if err is not None:
        return err
    cleaned, details = validate_email_password(data)
    if details:
        return bad_request(details=details)

    display_name = data.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        return bad_request(details={"display_name": "must be a string"})

    user = User(email=cleaned["email"], display_name=display_name)
    user.set_password(cleaned["password"])
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        # Duplicate email is enforced by the unique index, not by a
        # pre-check — a SELECT-then-INSERT race could let two simultaneous
        # signups both pass the check. The DB is the authority.
        db.session.rollback()
        return error(
            "Email already registered", 409, "Conflict",
            details={"email": "already registered"},
        )

    token, expires_in = mint_token(user)
    body = serialize_user(user)
    body["token"] = token
    body["expires_in"] = expires_in
    return body, 201


@api_bp.post("/auth/login")
def login():
    data, err = get_json_body()
    if err is not None:
        return err
    cleaned, details = validate_email_password(data)
    if details:
        return bad_request(details=details)

    user = db.session.execute(
        db.select(User).where(User.email == cleaned["email"])
    ).scalar_one_or_none()

    if user is None:
        # Dummy compare: same work, same 401, same message — login must
        # never reveal whether the email is registered (enumeration).
        bcrypt.checkpw(cleaned["password"].encode(), _DUMMY_HASH)
        return error("invalid email or password", 401, "Unauthorized")

    if not user.check_password(cleaned["password"]):
        return error("invalid email or password", 401, "Unauthorized")

    token, expires_in = mint_token(user)
    return {
        "token": token,
        "expires_in": expires_in,
        "user": serialize_user(user),
    }, 200
