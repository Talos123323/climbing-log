# TESTING.md — real test transcript

Everything below is output actually produced by running the commands
shown, on 2026-11-06 in this environment (Python 3.12.3, venv).
No output here is simulated, expected, or hand-written. Tokens are
truncated to 12 characters in the checks script; no full token or
secret appears in this file.

## 1. End-to-end checks (Flask test_client, testing config)

Command:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python tests/run_checks.py
```

Installed versions confirmed by `pip freeze` (direct deps):
Flask==3.0.3, Flask-SQLAlchemy==3.1.1, Flask-Migrate==4.0.7,
python-dotenv==1.0.1, PyJWT==2.9.0, bcrypt==4.1.2, gunicorn==22.0.0,
psycopg2-binary==2.9.9 (plus SQLAlchemy==2.1.8, alembic==1.20.1,
Werkzeug==3.1.9).

Output (`tests/run_checks.py`, exit code 0):

```
PASS: GET / -> 200 service climbing-log status=200 body={'api': '/api/health', 'docs': 'https://github.com/<you>/climbing-log', 'health': '/api/health', 'service': 'climbing-log'}
PASS: GET /api/health -> 200 ok/0.1.0 status=200 body={'status': 'ok', 'version': '0.1.0'}
PASS: register -> 201 with token + expires_in 43200 status=201 id=1 token=eyJhbGciOiJI... expires_in=43200
PASS: register duplicate email -> 409 status=409 body={'details': {'email': 'already registered'}, 'error': 'Conflict', 'message': 'Email already registered'}
PASS: register short password -> 400 details.password status=400 body={'details': {'password': 'must be at least 8 characters'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: register bad email -> 400 details.email status=400 body={'details': {'email': 'must be a valid email address'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: register missing password -> 400 status=400
PASS: passwords stored as salted bcrypt ($2b$12$, 60 chars, differ) hashes=['$2b$12$...', '$2b$12$...']
PASS: login -> 200 token + user status=200 expires_in=43200
PASS: login wrong password -> 401 'invalid email or password' status=401 body={'error': 'Unauthorized', 'message': 'invalid email or password'}
PASS: login unknown email -> 401 same message (no enumeration) status=401 body={'error': 'Unauthorized', 'message': 'invalid email or password'}
PASS: login missing password -> 400 status=400
PASS: GET /api/climbs no token -> 401 status=401
PASS: GET /api/climbs bad token -> 401 status=401
PASS: GET /api/profile no token -> 401 status=401
PASS: GET /api/profile -> 200, no password_hash status=200 body={'created_at': '2026-11-06T06:45:07.185988', 'display_name': 'Alice', 'email': 'a@example.com', 'id': 1, 'role': 'user'}
PASS: PUT /api/profile {} -> 400 status=400 body={'details': {'display_name': 'display_name is required'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: PUT /api/profile display_name -> 200 updated status=200 body={'created_at': '2026-11-06T06:45:07.185988', 'display_name': 'Alice Climbs', 'email': 'a@example.com', 'id': 1, 'role': 'user'}
PASS: PUT /api/profile display_name null -> 200 clears it status=200 body={'created_at': '2026-11-06T06:45:07.185988', 'display_name': None, 'email': 'a@example.com', 'id': 1, 'role': 'user'}
PASS: PUT /api/profile email -> 400 naming email status=400 body={'details': {'email': 'email cannot be changed here'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: PUT /api/profile password -> 400 naming password status=400 body={'details': {'password': 'password cannot be changed here'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: POST /api/climbs -> 201, Location header, owner from token status=201 id=1 Location=/api/climbs/1 user_id=1
PASS: POST /api/climbs minimal (optional fields omitted) -> 201 status=201
PASS: POST /api/climbs missing route_name -> 400 status=400 body={'details': {'route_name': 'route_name is required'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: POST /api/climbs bad outcome -> 400 details.outcome status=400 body={'details': {'outcome': 'must be one of: sent, attempted, projecting'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: user B creates own climb -> 201 status=201 id=3
PASS: GET /api/climbs page1 per_page2 -> 200, 2 items, total 5 pages 3 status=200 ids=[1, 2] total=5 pages=3
PASS: GET /api/climbs page2 -> 2 different items status=200 ids=[4, 5]
PASS: GET /api/climbs page3 -> 1 item (last page) status=200 ids=[6]
PASS: GET /api/climbs page past end -> 200 empty items, correct meta status=200 body={'items': [], 'page': 10, 'pages': 3, 'per_page': 2, 'total': 5}
PASS: GET /api/climbs per_page=0 -> 400 details.per_page status=400 body={'details': {'per_page': 'Must be at least 1'}, 'error': 'Bad Request', 'message': 'Invalid pagination parameters'}
PASS: GET /api/climbs per_page=51 -> 400 (max 50) status=400
PASS: GET /api/climbs page=0 -> 400 status=400
PASS: GET /api/climbs page=abc -> 400 status=400
PASS: GET /api/climbs as B -> only B's 1 climb status=200 total=1
PASS: GET own climb -> 200 status=200
PASS: GET other user's climb -> 404, same body as nonexistent 404 other=404 {'error': 'Not Found', 'message': 'Climb not found'} missing=404 {'error': 'Not Found', 'message': 'Climb not found'}
PASS: GET /api/climbs/abc -> 400 status=400 body={'details': {'id': 'Must be an integer'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: PUT own climb -> 200 grade V5, updated_at recomputed status=200 updated_at 2026-11-06T06:45:09.521021 -> 2026-11-06T06:45:10.559252
PASS: re-read after PUT -> persisted grade V5 status=200 grade=V5
PASS: PUT missing outcome -> 400 (full replacement, no merge) status=400 body={'details': {'outcome': 'must be one of: sent, attempted, projecting'}, 'error': 'Bad Request', 'message': 'Request validation failed'}
PASS: PUT other user's climb -> 404 status=404
PASS: PUT invalid outcome -> 400 rejected status=400
PASS: re-read after rejected PUT -> identical (no side effects) before=Blue Arete/2026-11-06T06:45:10.559252 after=Blue Arete/2026-11-06T06:45:10.559252
PASS: DELETE own climb -> 204 no body status=204 body=b''
PASS: GET after DELETE -> 404 status=404
PASS: second DELETE -> 404 status=404
PASS: DELETE other user's climb -> 404 status=404
PASS: GET /api/admin/users no token -> 401 status=401
PASS: GET /api/admin/users non-admin -> 403 Admin privileges required status=403 body={'error': 'Forbidden', 'message': 'Admin privileges required'}
PASS: GET /api/admin/users admin -> 200, no password_hash anywhere status=200 users=[{'created_at': '2026-11-06T06:45:07.185988', 'display_name': None, 'email': 'a@example.com', 'id': 1, 'role': 'admin'}, {'created_at': '2026-11-06T06:45:08.130434', 'display_name': None, 'email': 'b@example.com', 'id': 2, 'role': 'user'}]
PASS: demoted admin, same token -> 403 (role from DB, not JWT) status=403
PASS: unknown route -> 404 JSON envelope, no HTML status=404 body={'error': 'Not Found', 'message': 'The requested resource was not found'}
PASS: production_overrides missing vars -> RuntimeError naming both error=refusing to start in production; missing env vars: JWT_SECRET, DATABASE_URL
PASS: GET /api/health with unreachable DB -> 503 unhealthy status=503 body={'status': 'unhealthy'}

55 passed, 0 failed
```

## 2. Migrations (real, SQLite dev DB)

```bash
cp .env.example .env
python -m flask --app run.py db init
python -m flask --app run.py db migrate -m "Add users and climbs tables"
python -m flask --app run.py db upgrade
python -m flask --app run.py db current   # 38239713e8f3 (head)
```

Alembic detected both tables in one migration
(`migrations/versions/38239713e8f3_add_users_and_climbs_tables.py`):
users + climbs, index `ix_users_email`, index `ix_climbs_user_id`.
Verified schema after upgrade:

- tables: alembic_version, climbs, users
- users columns: id, email, password_hash, display_name, role, created_at
- climbs columns: id, user_id, route_name, grade, outcome,
  climbing_type, location, climbed_at, notes, created_at, updated_at
- alembic_version: 38239713e8f3

One migration covers both tables because both models were complete
when it was generated; the task's "users, then climbs/role" is the
content of that migration, not two separate files.

Secrets check (real):

```bash
$ git check-ignore -v .env
.gitignore:1:.env    .env
$ git ls-files | grep -i env
.env.example
```

Only `.env.example` is tracked; the local `.env` (dev-only values)
is ignored and was never committed.

## 3. Live server smoke test (real HTTP, Flask dev server)

```bash
.venv/bin/python run.py   # port 5000, development config, SQLite
```

Observed (token redacted here; the real run printed a full local
dev token, which is not reproduced):

- `GET /api/health` → `200 {"status": "ok", "version": "0.1.0"}`
- `POST /api/auth/register` (live@example.com) → `201`, `expires_in: 43200`
- `POST /api/climbs` (Blue... "Live Arete", V4, sent) → `201`,
  `Location: /api/climbs/1`, `user_id: 1`, `owner_id: 1`
- `GET /api/climbs?page=1&per_page=20` → `200`, `total: 1`, `pages: 1`,
  the created climb in `items`
- `GET /api/climbs/999` → `404`

## 4. Docker

Docker is NOT available in this build environment:

```bash
$ docker --version
/bin/bash: line 1: docker: command not found
$ which docker podman
(no output — neither is installed)
```

So `docker build` / `docker compose up` could NOT be verified here.
The Dockerfile and docker-compose.yml are written per the lessons
(layer ordering, non-root appuser, healthcheck, no `env_file` leak,
no migrations in CMD) but are unverified until run on a machine with
Docker — run `docker compose up --build` there before submitting,
and confirm `/api/health` returns 200. Do not treat this section as
a passing Docker check; it is an explicit gap.

## 5. One real failure found and fixed during testing

First run: 54 passed, 1 failed — the health-503 check returned 200.
Root cause was in the *test*, not the app: it mutated
`app.config["SQLALCHEMY_DATABASE_URI"]` after `create_app()`, but
Flask-SQLAlchemy binds the engine at app creation, so the old
in-memory engine was still in use and the check passed vacuously.
Fixed by registering a `BrokenDBConfig` subclass with the bad URI
*before* `create_app()`. Re-run: 55 passed, 0 failed.
