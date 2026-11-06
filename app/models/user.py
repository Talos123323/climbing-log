"""User model. Only a bcrypt hash is ever stored — there is no
password column. set_password / check_password are the only places
hashing happens, so a route can never accidentally store raw text.
"""

from datetime import datetime, timezone

import bcrypt

from ..extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # unique=True is the real 409 enforcement: the database itself rejects
    # a second row with the same email, so registration catches the
    # IntegrityError instead of a SELECT-then-INSERT race two signups
    # could both pass. nullable=False matters too — without it, multiple
    # NULL emails would be allowed (NULL != NULL).
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(80), nullable=True)
    # "user" by default; "admin" is set directly in the DB (there is no
    # public make-admin endpoint). Read fresh from the DB on every
    # request — never from the JWT payload.
    role = db.Column(db.String(20), nullable=False, default="user")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # One user has many climbs; Climb.user is the other side.
    climbs = db.relationship("Climb", back_populates="user", lazy="select")

    def set_password(self, raw: str) -> None:
        # gensalt() runs per call, so two accounts with the same password
        # get different hashes. bcrypt output is 60 chars, $2b$12$...
        self.password_hash = bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()

    def check_password(self, raw: str) -> bool:
        return bcrypt.checkpw(raw.encode(), self.password_hash.encode())
