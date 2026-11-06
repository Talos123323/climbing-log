# climbing-log

A JSON API for logging indoor climbs — one record per problem, with grade
and outcome (sent / attempted / projecting). Personal by design: every climb
belongs to the climber who logged it. If two climbers log the same gym
problem, those are two separate records, not one shared one.

Stack: Flask 3, Flask-SQLAlchemy, Flask-Migrate (Alembic), PyJWT, bcrypt,
gunicorn, Postgres in Docker Compose, SQLite for local dev.

## Quick start (Docker — the way a stranger should run it)

```bash
git clone https://github.com/Talos123323/climbing-log.git
cd climbing-log
cp .env.example .env
# Edit .env: set JWT_SECRET to a long random value and POSTGRES_PASSWORD.
docker compose up --build
docker compose run --rm web flask --app run.py db upgrade
curl http://localhost:8000/api/health
# {"status":"ok","version":"0.1.0"}
```

Data persists across restarts in the named volume `db_data`.
`docker compose down` keeps it; `docker compose down -v` deletes it.

## Quick start (local venv, SQLite)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env             # dev defaults work as-is for local use
flask --app run.py db upgrade
flask --app run.py run           # or: python run.py
curl http://localhost:5000/api/health
```

## Try it (curl)

```bash
BASE=http://localhost:8000   # or :5000 for the venv run

# Register (also mints a token) — save the token
curl -s -X POST $BASE/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"climber@example.com","password":"correct horse battery","display_name":"Alex"}'

TOKEN=<token from above>

# Log a climb (owner comes from the token, never the body)
curl -s -X POST $BASE/api/climbs -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"route_name":"Blue Arete","grade":"V4","outcome":"sent","climbing_type":"bouldering","location":"The Gym"}'

# List your climbs, page 1
curl -s "$BASE/api/climbs?page=1&per_page=20" -H "Authorization: Bearer $TOKEN"
```

## Environment variables

| Variable | Required | Default / example | Notes |
|---|---|---|---|
| `FLASK_CONFIG` | No | `development` | `development` / `testing` / `production` |
| `FLASK_APP` | No | `run.py` | Entry point for the `flask` CLI |
| `JWT_SECRET` | In production | `dev-only` (dev fallback) | Signs JWTs. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | In production | `sqlite:///dev.db` | Postgres in compose/deploy: `postgresql://user:password@host:5432/dbname` |
| `JWT_TTL_HOURS` | No | `12` | Token lifetime in hours |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Compose only | see `.env.example` | Must match the password inside `DATABASE_URL` |

Production refuses to start without `JWT_SECRET` and `DATABASE_URL`
(`production_overrides()` raises `RuntimeError` naming the missing ones).
There is no silent fallback to a public secret in production.

## Endpoints

| Method | Path | Auth | Success | Errors |
|---|---|---|---|---|
| GET | `/` | Public | 200 `{service, docs, health}` | — |
| GET | `/api/health` | Public | 200 `{status:"ok", version:"0.1.0"}` | 503 DB unreachable |
| POST | `/api/auth/register` | Public | 201 user + `token`, `expires_in` | 400 validation, 409 duplicate email |
| POST | `/api/auth/login` | Public | 200 `token`, `expires_in`, `user` | 400 validation, 401 bad credentials |
| GET | `/api/profile` | Logged-in | 200 profile | 401 |
| PUT | `/api/profile` | Logged-in | 200 updated profile (display_name only) | 400, 401 |
| POST | `/api/climbs` | Logged-in | 201 + `Location: /api/climbs/<id>` | 400, 401 |
| GET | `/api/climbs` | Logged-in | 200 `{items, page, per_page, total, pages}` | 400 bad pagination, 401 |
| GET | `/api/climbs/<id>` | Logged-in | 200 climb | 400 non-integer id, 401, 404 |
| PUT | `/api/climbs/<id>` | Logged-in | 200 updated climb | 400, 401, 404 |
| DELETE | `/api/climbs/<id>` | Logged-in | 204 no body | 400, 401, 404 |
| GET | `/api/admin/users` | Admin-only | 200 user list (no password hashes) | 401 no/bad token, 403 not admin |

List defaults: `?page=1&per_page=20`, `per_page` max 50. A page past the
end returns 200 with empty `items` and correct metadata — not 404.

## Errors

Every error — including unknown routes (404), wrong method (405), and
server errors (500) — uses one JSON envelope, never HTML:

```json
{"error": "Bad Request", "message": "Request validation failed",
 "details": {"outcome": "must be one of: sent, attempted, projecting"}}
```

`details` is present only when there is field-level information.
No response ever contains a password or password hash.

## Ownership — the one decision that shapes everything

Ownership is a **scoping filter, never a permission check**. Every climb
query is `WHERE id = ? AND user_id = ?` (the user id comes from the
token, never the request body). So:

- "Doesn't exist" and "belongs to someone else" return the **same 404**
  with the same body. Answering 403 for someone else's record would
  confirm that record exists — a small leak. There is **no 403 anywhere
  on climbs**.
- The admin route is the opposite: `GET /api/admin/users` returns
  **403** for a valid token whose role is not `admin`, because there the
  resource exists and the caller is known — the denial is about role,
  not about hiding existence. And the role is read fresh from the
  database on every request, never from the JWT payload, so demoting a
  user takes effect on their next request.
- `PUT /api/climbs/<id>` is a **full replacement**: missing `route_name`
  or `outcome` is 400, and optional fields absent from the body are set
  to `null` — it never merges. `PUT /api/profile` is the same, except
  `{}` is 400 while `{"display_name": null}` validly clears the name.
- A second `DELETE` returns **404**, not a second 204: the record is
  gone, so "not found" is the honest answer.
- Login collapses wrong-email and wrong-password into one 401 with the
  same message (`invalid email or password`), with a dummy bcrypt
  compare when the email is not found — otherwise login becomes an
  account-enumeration oracle.
- There is **no logout endpoint** and no `/api/users/<id>` endpoint.
  Tokens are bearer tokens with no server session (expiry + re-login
  is the honest model for v1); a user collection would contradict the
  ownership model.

## Migrations

```bash
flask --app run.py db init            # once, already done in this repo
flask --app run.py db migrate -m "Add users and climbs tables"
flask --app run.py db upgrade
```

Migrations are committed in `migrations/`. They are **not** run in the
Docker `CMD`: with 3 gunicorn workers they would race on the
`alembic_version` table. Run them once before starting (see Quick start),
or as a pre-deploy hook — see Deployment.

## Tests

```bash
python tests/run_checks.py
# 55 passed, 0 failed  (real output is saved in TESTING.md)
```

The script uses Flask's test client against the testing config
(in-memory SQLite) and covers: health (200 + 503), register (201 / 409 /
400), login (200 / 401 collapsed), auth gates (401), profile GET/PUT,
climb CRUD, pagination (pages 1–3, past-the-end, invalid values),
ownership 404s (identical body for missing vs. someone else's),
rejected-mutation side-effect proof (re-read identical), DELETE 204
then 404, admin 401/403/200, role-from-DB demotion, and the
production fail-fast. See `TESTING.md` for the full real transcript.

## Deployment (Render + Neon)

1. Push this repo to GitHub (public).
2. **Neon**: create a Postgres database, copy its connection string.
   It must be `postgresql://user:password@host/dbname` — **not**
   `postgresql+psycopg://`, because this project uses `psycopg2-binary`,
   and the `+psycopg://` scheme needs the `psycopg` (v3) driver.
   Append `?sslmode=require` (Neon requires SSL).
3. **Render**: New → Web Service → build from the GitHub repo,
   Environment: **Docker**. Render injects `PORT` itself.
4. Set the Render **Pre-Deploy Command** to:
   `flask --app run.py db upgrade`
   (runs migrations once, before the new version starts — never in CMD).
5. Environment variables on Render:
   - `DATABASE_URL` — the Neon string from step 2
   - `JWT_SECRET` — a long random secret (generate as above)
   - `FLASK_CONFIG` — `production`
   - Do **not** set `PORT` yourself; Render provides it.
6. Deploy, then verify against the live URL:
   `curl https://<your-service>.onrender.com/api/health`
   then register / login / create a climb as in "Try it" above.

## Project layout

```
climbing-log/
├── run.py                  # entry point; gunicorn target is run:app
├── app/
│   ├── __init__.py         # create_app() factory + error handlers
│   ├── config.py           # Base/Development/Testing/Production + CONFIG_MAP
│   ├── extensions.py       # unbound db + migrate
│   ├── models/
│   │   ├── user.py         # User + bcrypt set/check_password
│   │   └── climb.py        # Climb + OUTCOMES check constraint
│   └── api/
│       ├── __init__.py     # api_bp blueprint
│       ├── helpers.py      # error envelope, mint_token, token_required,
│       │                   # require_admin, serializers, validators
│       ├── health.py       # GET /api/health
│       ├── auth.py         # register / login
│       ├── profile.py      # GET / PUT /api/profile
│       ├── climbs.py       # climbs CRUD
│       └── admin.py        # GET /api/admin/users
├── migrations/             # Alembic migrations (committed)
├── tests/run_checks.py     # real end-to-end checks (test_client)
├── Dockerfile              # python:3.12-slim, non-root appuser, gunicorn
├── docker-compose.yml      # web + postgres:16 with healthcheck
├── requirements.txt        # pinned direct dependencies
└── TESTING.md              # real test transcript
```
