"""Climbs — full CRUD for the caller's own climbs.

One rule governs every endpoint here: ownership is a scoping filter,
never a permission check. Every query is WHERE id = ? AND user_id = ?,
so "doesn't exist" and "belongs to someone else" produce the identical
404 — there is no code path that can distinguish them from the outside,
and no 403 anywhere on climbs.
"""

from datetime import datetime, timezone

from flask import g, request

from ..extensions import db
from ..models.climb import Climb
from . import api_bp
from .helpers import (
    bad_request,
    get_json_body,
    not_found,
    parse_int_id,
    parse_pagination,
    serialize_climb,
    token_required,
    validate_climb,
)


def _scoped_climb(climb_id):
    """Fetch one climb owned by the caller, or None (404 either way)."""
    return db.session.execute(
        db.select(Climb).where(
            Climb.id == climb_id, Climb.user_id == g.current_user.id
        )
    ).scalar_one_or_none()


@api_bp.post("/climbs")
@token_required
def create_climb():
    data, err = get_json_body()
    if err is not None:
        return err
    cleaned, details = validate_climb(data)
    if details:
        return bad_request(details=details)

    # Owner comes from the token, never the body. Body owner_id / id /
    # created_at are ignored by the validator's design (they are not
    # read here at all), so a client round-tripping a fetched object
    # cannot claim someone else's record.
    climb = Climb(user_id=g.current_user.id, **cleaned)
    db.session.add(climb)
    db.session.commit()
    response = serialize_climb(climb)
    return response, 201, {"Location": f"/api/climbs/{climb.id}"}


@api_bp.get("/climbs")
@token_required
def list_climbs():
    page, per_page, err = parse_pagination()
    if err is not None:
        return err
    # Ownership is the filter: only the caller's rows are ever queried.
    query = (
        db.select(Climb)
        .where(Climb.user_id == g.current_user.id)
        .order_by(Climb.id)
    )
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    total = pagination.total
    pages = (total + per_page - 1) // per_page if total else 0
    # A page past the end is 200 with empty items and correct metadata,
    # NOT 404 — the collection exists; that slice is just empty.
    return {
        "items": [serialize_climb(c) for c in pagination.items],
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
    }, 200


@api_bp.get("/climbs/<climb_id>")
@token_required
def get_climb(climb_id):
    climb_id, err = parse_int_id(climb_id)
    if err is not None:
        return err
    climb = _scoped_climb(climb_id)
    if climb is None:
        return not_found()
    return serialize_climb(climb), 200


@api_bp.put("/climbs/<climb_id>")
@token_required
def update_climb(climb_id):
    climb_id, err = parse_int_id(climb_id)
    if err is not None:
        return err
    climb = _scoped_climb(climb_id)
    if climb is None:
        return not_found()
    data, err = get_json_body()
    if err is not None:
        return err
    # Same validator as POST — literally the same function, so the 400
    # shape is identical and "is this a valid climb" is defined once.
    # Full replacement: missing route_name/outcome is 400, and optional
    # fields absent from the body are set to None (not merged).
    cleaned, details = validate_climb(data)
    if details:
        return bad_request(details=details)
    for key, value in cleaned.items():
        setattr(climb, key, value)
    climb.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return serialize_climb(climb), 200


@api_bp.delete("/climbs/<climb_id>")
@token_required
def delete_climb(climb_id):
    climb_id, err = parse_int_id(climb_id)
    if err is not None:
        return err
    climb = _scoped_climb(climb_id)
    if climb is None:
        return not_found()
    db.session.delete(climb)
    db.session.commit()
    # 204, no body. A second DELETE hits the same scoped query, finds
    # nothing, and returns 404 — the record is gone, so "not found"
    # is the honest answer, not a second success.
    return "", 204
