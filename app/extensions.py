"""Unbound extensions.

Nothing is instantiated with an app here — the factory in app/__init__.py
calls init_app() on these. Keeping them unbound is what makes
create_app("testing") / create_app("production") possible.
"""

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
