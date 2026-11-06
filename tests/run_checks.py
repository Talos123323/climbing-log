"""Real end-to-end checks for climbing-log, using Flask's test_client
against the testing config (in-memory SQLite).

Run:  python tests/run_checks.py
Exit code 0 = every check passed. Anything else = a real failure
to fix in the code — never edit this script to print PASS anyway.

Tokens are redacted in output (first 12 chars only); no secrets printed.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import production_overrides  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.user import User  # noqa: E402

PASS = 0
FAIL = 0
FAILURES = []


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"PASS: {name} {detail}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL: {name} {detail}")


def short(token):
    return (token or "")[:12] + "..."


def main():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        client = app.test_client()

        # ---------- root + health ----------
        r = client.get("/")
        check("GET / -> 200 service climbing-log",
              r.status_code == 200 and r.get_json().get("service") == "climbing-log",
              f"status={r.status_code} body={r.get_json()}")
        r = client.get("/api/health")
        check("GET /api/health -> 200 ok/0.1.0",
              r.status_code == 200
              and r.get_json() == {"status": "ok", "version": "0.1.0"},
              f"status={r.status_code} body={r.get_json()}")

        # ---------- register ----------
        r = client.post("/api/auth/register", json={
            "email": "a@example.com", "password": "correct horse battery",
            "display_name": "Alice"})
        body = r.get_json() or {}
        check("register -> 201 with token + expires_in 43200",
              r.status_code == 201 and body.get("email") == "a@example.com"
              and body.get("role") == "user" and body.get("expires_in") == 43200
              and body.get("token"),
              f"status={r.status_code} id={body.get('id')} token={short(body.get('token'))} expires_in={body.get('expires_in')}")
        token_a = body.get("token")
        user_a_id = body.get("id")

        r = client.post("/api/auth/register", json={
            "email": "a@example.com", "password": "correct horse battery"})
        check("register duplicate email -> 409",
              r.status_code == 409 and r.get_json().get("error") == "Conflict",
              f"status={r.status_code} body={r.get_json()}")
        r = client.post("/api/auth/register", json={
            "email": "short@example.com", "password": "short"})
        check("register short password -> 400 details.password",
              r.status_code == 400
              and "password" in (r.get_json() or {}).get("details", {}),
              f"status={r.status_code} body={r.get_json()}")
        r = client.post("/api/auth/register", json={
            "email": "not-an-email", "password": "correct horse battery"})
        check("register bad email -> 400 details.email",
              r.status_code == 400
              and "email" in (r.get_json() or {}).get("details", {}),
              f"status={r.status_code} body={r.get_json()}")
        r = client.post("/api/auth/register", json={"email": "x@example.com"})
        check("register missing password -> 400",
              r.status_code == 400, f"status={r.status_code}")

        # bcrypt stored correctly (same password, different salts)
        r = client.post("/api/auth/register", json={
            "email": "b@example.com", "password": "correct horse battery"})
        body_b = r.get_json() or {}
        token_b = body_b.get("token")
        user_b_id = body_b.get("id")
        hashes = [u.password_hash for u in
                  db.session.execute(db.select(User)).scalars().all()]
        check("passwords stored as salted bcrypt ($2b$12$, 60 chars, differ)",
              len(hashes) == 2 and all(
                  h.startswith("$2b$12$") and len(h) == 60 for h in hashes)
              and hashes[0] != hashes[1],
              f"hashes={[h[:7] + '...' for h in hashes]}")

        # ---------- login ----------
        r = client.post("/api/auth/login", json={
            "email": "a@example.com", "password": "correct horse battery"})
        lb = r.get_json() or {}
        check("login -> 200 token + user",
              r.status_code == 200 and lb.get("token")
              and lb.get("user", {}).get("email") == "a@example.com"
              and "password_hash" not in str(lb),
              f"status={r.status_code} expires_in={lb.get('expires_in')}")
        r = client.post("/api/auth/login", json={
            "email": "a@example.com", "password": "wrong password here"})
        check("login wrong password -> 401 'invalid email or password'",
              r.status_code == 401
              and r.get_json().get("message") == "invalid email or password",
              f"status={r.status_code} body={r.get_json()}")
        r = client.post("/api/auth/login", json={
            "email": "nobody@example.com", "password": "wrong password here"})
        check("login unknown email -> 401 same message (no enumeration)",
              r.status_code == 401
              and r.get_json().get("message") == "invalid email or password",
              f"status={r.status_code} body={r.get_json()}")
        r = client.post("/api/auth/login", json={"email": "a@example.com"})
        check("login missing password -> 400",
              r.status_code == 400, f"status={r.status_code}")

        # ---------- auth gate ----------
        r = client.get("/api/climbs")
        check("GET /api/climbs no token -> 401",
              r.status_code == 401, f"status={r.status_code}")
        r = client.get("/api/climbs", headers={"Authorization": "Bearer bogus"})
        check("GET /api/climbs bad token -> 401",
              r.status_code == 401, f"status={r.status_code}")
        r = client.get("/api/profile")
        check("GET /api/profile no token -> 401",
              r.status_code == 401, f"status={r.status_code}")

        ha = {"Authorization": f"Bearer {token_a}"}
        hb = {"Authorization": f"Bearer {token_b}"}

        # ---------- profile ----------
        r = client.get("/api/profile", headers=ha)
        pb = r.get_json() or {}
        check("GET /api/profile -> 200, no password_hash",
              r.status_code == 200 and pb.get("email") == "a@example.com"
              and "password_hash" not in pb and pb.get("role") == "user",
              f"status={r.status_code} body={pb}")
        r = client.put("/api/profile", headers=ha, json={})
        check("PUT /api/profile {} -> 400",
              r.status_code == 400, f"status={r.status_code} body={r.get_json()}")
        r = client.put("/api/profile", headers=ha,
                       json={"display_name": "Alice Climbs"})
        check("PUT /api/profile display_name -> 200 updated",
              r.status_code == 200
              and r.get_json().get("display_name") == "Alice Climbs",
              f"status={r.status_code} body={r.get_json()}")
        r = client.put("/api/profile", headers=ha, json={"display_name": None})
        check("PUT /api/profile display_name null -> 200 clears it",
              r.status_code == 200 and r.get_json().get("display_name") is None,
              f"status={r.status_code} body={r.get_json()}")
        r = client.put("/api/profile", headers=ha,
                       json={"email": "new@example.com"})
        check("PUT /api/profile email -> 400 naming email",
              r.status_code == 400
              and "email" in (r.get_json() or {}).get("details", {}),
              f"status={r.status_code} body={r.get_json()}")
        r = client.put("/api/profile", headers=ha,
                       json={"password": "new password here"})
        check("PUT /api/profile password -> 400 naming password",
              r.status_code == 400
              and "password" in (r.get_json() or {}).get("details", {}),
              f"status={r.status_code} body={r.get_json()}")

        # ---------- climbs: create ----------
        r = client.post("/api/climbs", headers=ha, json={
            "route_name": "Blue Arete", "grade": "V4", "outcome": "sent",
            "climbing_type": "bouldering", "location": "The Gym",
            "notes": "first try", "owner_id": 999, "id": 999})
        cb = r.get_json() or {}
        check("POST /api/climbs -> 201, Location header, owner from token",
              r.status_code == 201 and cb.get("user_id") == user_a_id
              and cb.get("owner_id") == user_a_id and cb.get("id") != 999
              and r.headers.get("Location") == f"/api/climbs/{cb.get('id')}",
              f"status={r.status_code} id={cb.get('id')} Location={r.headers.get('Location')} user_id={cb.get('user_id')}")
        climb1 = cb.get("id")
        r = client.post("/api/climbs", headers=ha, json={
            "route_name": "Red Slab", "grade": "V3", "outcome": "attempted"})
        check("POST /api/climbs minimal (optional fields omitted) -> 201",
              r.status_code == 201, f"status={r.status_code}")
        climb2 = (r.get_json() or {}).get("id")
        r = client.post("/api/climbs", headers=ha, json={
            "grade": "V4", "outcome": "sent"})
        check("POST /api/climbs missing route_name -> 400",
              r.status_code == 400, f"status={r.status_code} body={r.get_json()}")
        r = client.post("/api/climbs", headers=ha, json={
            "route_name": "X", "outcome": "fell"})
        check("POST /api/climbs bad outcome -> 400 details.outcome",
              r.status_code == 400
              and "outcome" in (r.get_json() or {}).get("details", {}),
              f"status={r.status_code} body={r.get_json()}")
        r = client.post("/api/climbs", headers=hb, json={
            "route_name": "B's Problem", "grade": "V5", "outcome": "projecting"})
        climb_b = (r.get_json() or {}).get("id")
        check("user B creates own climb -> 201",
              r.status_code == 201, f"status={r.status_code} id={climb_b}")

        # more climbs for A (total A = 5) for pagination
        for name in ("Green Traverse", "Yellow Roof", "Black Crack"):
            client.post("/api/climbs", headers=ha, json={
                "route_name": name, "outcome": "attempted"})

        # ---------- climbs: list + pagination ----------
        r = client.get("/api/climbs?page=1&per_page=2", headers=ha)
        lb1 = r.get_json() or {}
        check("GET /api/climbs page1 per_page2 -> 200, 2 items, total 5 pages 3",
              r.status_code == 200 and len(lb1.get("items", [])) == 2
              and lb1.get("total") == 5 and lb1.get("pages") == 3
              and lb1.get("page") == 1 and lb1.get("per_page") == 2,
              f"status={r.status_code} ids={[i['id'] for i in lb1.get('items', [])]} total={lb1.get('total')} pages={lb1.get('pages')}")
        r = client.get("/api/climbs?page=2&per_page=2", headers=ha)
        lb2 = r.get_json() or {}
        ids1 = {i["id"] for i in lb1.get("items", [])}
        ids2 = {i["id"] for i in lb2.get("items", [])}
        check("GET /api/climbs page2 -> 2 different items",
              r.status_code == 200 and len(lb2.get("items", [])) == 2
              and not (ids1 & ids2),
              f"status={r.status_code} ids={[i['id'] for i in lb2.get('items', [])]}")
        r = client.get("/api/climbs?page=3&per_page=2", headers=ha)
        lb3 = r.get_json() or {}
        check("GET /api/climbs page3 -> 1 item (last page)",
              r.status_code == 200 and len(lb3.get("items", [])) == 1,
              f"status={r.status_code} ids={[i['id'] for i in lb3.get('items', [])]}")
        r = client.get("/api/climbs?page=10&per_page=2", headers=ha)
        lb10 = r.get_json() or {}
        check("GET /api/climbs page past end -> 200 empty items, correct meta",
              r.status_code == 200 and lb10.get("items") == []
              and lb10.get("total") == 5 and lb10.get("pages") == 3,
              f"status={r.status_code} body={lb10}")
        r = client.get("/api/climbs?per_page=0", headers=ha)
        check("GET /api/climbs per_page=0 -> 400 details.per_page",
              r.status_code == 400
              and "per_page" in (r.get_json() or {}).get("details", {}),
              f"status={r.status_code} body={r.get_json()}")
        r = client.get("/api/climbs?per_page=51", headers=ha)
        check("GET /api/climbs per_page=51 -> 400 (max 50)",
              r.status_code == 400, f"status={r.status_code}")
        r = client.get("/api/climbs?page=0", headers=ha)
        check("GET /api/climbs page=0 -> 400",
              r.status_code == 400, f"status={r.status_code}")
        r = client.get("/api/climbs?page=abc", headers=ha)
        check("GET /api/climbs page=abc -> 400",
              r.status_code == 400, f"status={r.status_code}")
        r = client.get("/api/climbs", headers=hb)
        lb_b = r.get_json() or {}
        check("GET /api/climbs as B -> only B's 1 climb",
              r.status_code == 200 and lb_b.get("total") == 1
              and lb_b["items"][0]["id"] == climb_b,
              f"status={r.status_code} total={lb_b.get('total')}")

        # ---------- climbs: single read / ownership ----------
        r = client.get(f"/api/climbs/{climb1}", headers=ha)
        check("GET own climb -> 200",
              r.status_code == 200 and r.get_json().get("id") == climb1,
              f"status={r.status_code}")
        r = client.get(f"/api/climbs/{climb_b}", headers=ha)
        rb_other = r.get_json() or {}
        r2 = client.get("/api/climbs/999999", headers=ha)
        check("GET other user's climb -> 404, same body as nonexistent 404",
              r.status_code == 404 and rb_other == (r2.get_json() or {}),
              f"other={r.status_code} {rb_other} missing={r2.status_code} {r2.get_json()}")
        r = client.get("/api/climbs/abc", headers=ha)
        check("GET /api/climbs/abc -> 400",
              r.status_code == 400, f"status={r.status_code} body={r.get_json()}")

        # ---------- climbs: PUT ----------
        r = client.get(f"/api/climbs/{climb1}", headers=ha)
        before = r.get_json() or {}
        time.sleep(1)
        r = client.put(f"/api/climbs/{climb1}", headers=ha, json={
            "route_name": "Blue Arete", "grade": "V5", "outcome": "sent",
            "climbing_type": "bouldering", "location": "The Gym",
            "notes": "sent clean"})
        ub = r.get_json() or {}
        check("PUT own climb -> 200 grade V5, updated_at recomputed",
              r.status_code == 200 and ub.get("grade") == "V5"
              and ub.get("updated_at") > before.get("updated_at"),
              f"status={r.status_code} updated_at {before.get('updated_at')} -> {ub.get('updated_at')}")
        r = client.get(f"/api/climbs/{climb1}", headers=ha)
        check("re-read after PUT -> persisted grade V5",
              r.status_code == 200 and r.get_json().get("grade") == "V5",
              f"status={r.status_code} grade={r.get_json().get('grade')}")
        r = client.put(f"/api/climbs/{climb1}", headers=ha, json={
            "route_name": "Blue Arete"})
        check("PUT missing outcome -> 400 (full replacement, no merge)",
              r.status_code == 400, f"status={r.status_code} body={r.get_json()}")
        r = client.put(f"/api/climbs/{climb_b}", headers=ha, json={
            "route_name": "Hijack", "outcome": "sent"})
        check("PUT other user's climb -> 404",
              r.status_code == 404, f"status={r.status_code}")

        # rejected mutation must have no side effects
        r = client.get(f"/api/climbs/{climb1}", headers=ha)
        pre = r.get_json() or {}
        r = client.put(f"/api/climbs/{climb1}", headers=ha, json={
            "route_name": "MUTATED", "outcome": "fell"})
        check("PUT invalid outcome -> 400 rejected",
              r.status_code == 400, f"status={r.status_code}")
        r = client.get(f"/api/climbs/{climb1}", headers=ha)
        post = r.get_json() or {}
        check("re-read after rejected PUT -> identical (no side effects)",
              post.get("route_name") == pre.get("route_name")
              and post.get("updated_at") == pre.get("updated_at")
              and post.get("grade") == pre.get("grade"),
              f"before={pre.get('route_name')}/{pre.get('updated_at')} after={post.get('route_name')}/{post.get('updated_at')}")

        # ---------- climbs: DELETE ----------
        r = client.delete(f"/api/climbs/{climb2}", headers=ha)
        check("DELETE own climb -> 204 no body",
              r.status_code == 204 and r.data == b"",
              f"status={r.status_code} body={r.data!r}")
        r = client.get(f"/api/climbs/{climb2}", headers=ha)
        check("GET after DELETE -> 404",
              r.status_code == 404, f"status={r.status_code}")
        r = client.delete(f"/api/climbs/{climb2}", headers=ha)
        check("second DELETE -> 404",
              r.status_code == 404, f"status={r.status_code}")
        r = client.delete(f"/api/climbs/{climb_b}", headers=ha)
        check("DELETE other user's climb -> 404",
              r.status_code == 404, f"status={r.status_code}")

        # ---------- admin ----------
        r = client.get("/api/admin/users")
        check("GET /api/admin/users no token -> 401",
              r.status_code == 401, f"status={r.status_code}")
        r = client.get("/api/admin/users", headers=ha)
        check("GET /api/admin/users non-admin -> 403 Admin privileges required",
              r.status_code == 403
              and r.get_json().get("message") == "Admin privileges required",
              f"status={r.status_code} body={r.get_json()}")
        # Make A an admin directly in the DB (no public endpoint for this).
        user_a = db.session.get(User, user_a_id)
        user_a.role = "admin"
        db.session.commit()
        r = client.get("/api/admin/users", headers=ha)
        ab = r.get_json() or []
        check("GET /api/admin/users admin -> 200, no password_hash anywhere",
              r.status_code == 200 and isinstance(ab, list) and len(ab) == 2
              and all("password_hash" not in u for u in ab)
              and {u["email"] for u in ab} == {"a@example.com", "b@example.com"},
              f"status={r.status_code} users={ab}")
        # Role is read from the DB, not the JWT: demote and the same
        # (still unexpired) token must now get 403.
        user_a.role = "user"
        db.session.commit()
        r = client.get("/api/admin/users", headers=ha)
        check("demoted admin, same token -> 403 (role from DB, not JWT)",
              r.status_code == 403, f"status={r.status_code}")

        # ---------- error envelope on unknown route ----------
        r = client.get("/api/nope", headers=ha)
        check("unknown route -> 404 JSON envelope, no HTML",
              r.status_code == 404 and r.get_json().get("error") == "Not Found"
              and b"<html" not in r.data.lower(),
              f"status={r.status_code} body={r.get_json()}")

        # ---------- production fail-fast ----------
        saved = {k: os.environ.get(k) for k in ("JWT_SECRET", "DATABASE_URL")}
        os.environ.pop("JWT_SECRET", None)
        os.environ.pop("DATABASE_URL", None)
        try:
            production_overrides()
            check("production_overrides missing vars -> RuntimeError", False)
        except RuntimeError as exc:
            msg = str(exc)
            check("production_overrides missing vars -> RuntimeError naming both",
                  "JWT_SECRET" in msg and "DATABASE_URL" in msg,
                  f"error={msg}")
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    # ---------- health 503 when the DB is unreachable ----------
    # The DB URI must be set BEFORE create_app: Flask-SQLAlchemy binds
    # the engine at app creation, so mutating config afterwards (an
    # earlier draft of this check did exactly that) leaves the old
    # in-memory engine in place and the check passes vacuously.
    from app.config import CONFIG_MAP, TestingConfig  # noqa: E402

    class BrokenDBConfig(TestingConfig):
        SQLALCHEMY_DATABASE_URI = "sqlite:////nonexistent-dir-xyz/db.sqlite"

    CONFIG_MAP["broken-test-only"] = BrokenDBConfig
    app2 = create_app("broken-test-only")
    with app2.app_context():
        r = app2.test_client().get("/api/health")
        check("GET /api/health with unreachable DB -> 503 unhealthy",
              r.status_code == 503 and r.get_json().get("status") == "unhealthy",
              f"status={r.status_code} body={r.get_json()}")

    print(f"\n{PASS} passed, {FAIL} failed")
    if FAILURES:
        print("Failures:", FAILURES)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
