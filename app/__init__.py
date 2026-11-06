"""Flask application factory."""

from flask import Flask, jsonify

from .config import CONFIG_MAP, production_overrides
from .extensions import db, migrate


def create_app(config_name="development"):
    """Build and return a Flask app for the named config.

    Raises ValueError for an unknown config name, and RuntimeError
    (from production_overrides) if production is selected without
    JWT_SECRET / DATABASE_URL set.
    """
    if config_name not in CONFIG_MAP:
        raise ValueError(f"unknown config: {config_name!r}")

    app = Flask(__name__)
    app.config.from_object(CONFIG_MAP[config_name])

    if config_name == "production":
        app.config.from_mapping(production_overrides())

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Alembic sees them (db.metadata must include
    # users + climbs or `flask db migrate` generates an empty migration).
    from . import models  # noqa: F401

    from .api import api_bp

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/")
    def index():
        return jsonify(
            service="climbing-log",
            docs="https://github.com/Talos123323/climbing-log",
            health="/api/health",
            api="/api/health",
        ), 200

    # --- Error handlers: JSON envelope everywhere, never HTML. ---
    @app.errorhandler(404)
    def handle_404(error):
        return (
            jsonify(error="Not Found", message="The requested resource was not found"),
            404,
        )

    @app.errorhandler(405)
    def handle_405(error):
        return (
            jsonify(error="Method Not Allowed", message="Method not allowed for this resource"),
            405,
        )

    @app.errorhandler(500)
    def handle_500(error):
        db.session.rollback()
        return (
            jsonify(error="Internal Server Error", message="An unexpected error occurred"),
            500,
        )

    return app
