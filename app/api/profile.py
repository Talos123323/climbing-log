"""Profile: read and update the caller's own profile.

PUT is display_name only. Email/password changes are out of scope —
email needs verification, password needs a current-password flow —
so sending them is a 400 naming the field, not a silent ignore.
"""

from flask import g

from ..extensions import db
from . import api_bp
from .helpers import bad_request, get_json_body, serialize_user, token_required


@api_bp.get("/profile")
@token_required
def get_profile():
    return serialize_user(g.current_user), 200


@api_bp.put("/profile")
@token_required
def update_profile():
    data, err = get_json_body()
    if err is not None:
        return err

    # Rejected, with the field named: the client has real intent to
    # change these, and ignoring them would leave the user believing
    # the change landed until their next failed login.
    for field in ("email", "password"):
        if field in data:
            return bad_request(
                details={field: f"{field} cannot be changed here"}
            )
    for field in data:
        if field != "display_name":
            return bad_request(details={field: "field cannot be changed"})

    # Absent != null: {} is a 400 (the field being replaced was not
    # sent); {"display_name": null} is valid and clears the name.
    if "display_name" not in data:
        return bad_request(details={"display_name": "display_name is required"})

    display_name = data["display_name"]
    if display_name is not None:
        if not isinstance(display_name, str):
            return bad_request(details={"display_name": "must be a string"})
        if len(display_name) > 80:
            return bad_request(
                details={"display_name": "must be at most 80 characters"}
            )

    g.current_user.display_name = display_name
    db.session.commit()
    return serialize_user(g.current_user), 200
