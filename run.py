"""Entry point.

Loads .env, then builds the app. Gunicorn runs this module as
`gunicorn ... run:app` — there is no separate wsgi.py.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402

app = create_app(os.environ.get("FLASK_CONFIG", "development"))

if __name__ == "__main__":
    app.run()
