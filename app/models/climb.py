"""Climb model — the core resource.

One record = one individual problem/route a climber logged. It is owned
by exactly one user and private to them: if two climbers log the same
gym problem, those are two separate records, not one shared one.
"""

from datetime import datetime, timezone

from ..extensions import db

OUTCOMES = ("sent", "attempted", "projecting")


class Climb(db.Model):
    __tablename__ = "climbs"

    id = db.Column(db.Integer, primary_key=True)
    # Owner. NOT NULL, foreign key to users.id; deleting a user cascades.
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    route_name = db.Column(db.String(255), nullable=False)
    # Grade is a small ordered scale, not a number ("V4", "5.10a") —
    # stored as free text in v1.
    grade = db.Column(db.String(32), nullable=True)
    outcome = db.Column(db.String(16), nullable=False)
    climbing_type = db.Column(db.String(32), nullable=True)  # bouldering / sport / ...
    location = db.Column(db.String(255), nullable=True)  # gym or crag
    climbed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship("User", back_populates="climbs")

    __table_args__ = (
        db.CheckConstraint(
            "outcome IN ('sent', 'attempted', 'projecting')",
            name="ck_climbs_outcome",
        ),
    )
