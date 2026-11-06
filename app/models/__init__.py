"""Models package. Importing both models here is what makes Alembic
see them — an empty __init__.py yields an empty migration with no error.
"""

from .climb import Climb  # noqa: F401
from .user import User  # noqa: F401

__all__ = ["User", "Climb"]
