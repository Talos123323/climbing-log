FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Create the non-root user BEFORE copying code, so the copy can be
# owned by them (see chown below) and the app never runs as root.
RUN useradd --uid 10001 --create-home appuser

# Dependency layer first: COPY requirements + pip install BEFORE
# COPY . . so a code edit does not invalidate the pip cache layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# exec-form CMD cannot expand $PORT, hence sh -c "exec ...": the shell
# expands ${PORT:-8000}, and exec makes gunicorn PID 1 so it receives
# SIGTERM cleanly on shutdown.
# run:app is the target — run.py exposes `app` at module level; there
# is no separate wsgi.py.
# NOTE: `flask db upgrade` is deliberately NOT in this CMD. With 3
# workers it would race on the alembic_version table. Run migrations
# once, before starting, e.g.:
#   docker compose run --rm web flask --app run.py db upgrade
# (or as the Render Pre-Deploy Command on deploy.)
CMD ["sh", "-c", "exec gunicorn -b 0.0.0.0:${PORT:-8000} --workers 3 run:app"]
