# EXPLAIN.md — study guide for the final review

The final review asks three open-ended questions about *your own*
project code. This guide is one paragraph per design decision, in the
language you used when you designed it. If you can say each paragraph
in your own words, you can answer those questions.

## Why 404, not 403, for someone else's climb

A climb is a personal log entry, private to the climber who logged it.
If `GET /api/climbs/<id>` returned 403 for a record that exists but
belongs to someone else, and 404 for one that does not exist, the status
code itself would tell an attacker which ids are real — a small leak.
So ownership is enforced as a scoping filter, not a permission check:
every climb query is `WHERE id = ? AND user_id = ?`, with the user id
taken from the token. "Doesn't exist" and "not mine" hit the same code
path and return the same 404 with the same body, and there is no code
path anywhere on climbs that can answer 403.

## Why 403 for the admin route, then

The admin route is a different situation, so it gets a different
answer. `GET /api/admin/users` is a real collection that exists, and
the caller is already authenticated — the only question is whether
their role allows it. Hiding the route's existence would buy nothing,
and merging 401 (bad token) with 403 (wrong role) would make debugging
and client retry logic worse: a 401 means "get a new token", a 403
means "this account will never be allowed". So the token check owns
the 401 and the role check owns the 403, in one decorator
(`require_admin`) instead of an `if` copied into every handler.

## Why the role comes from the database, not the JWT

The token payload carries only `sub`, `iat`, and `exp` — deliberately
no role. If the role lived in the token, demoting an admin would do
nothing until their token expired (up to 12 hours). Because
`token_required` loads the user row from the database on every request
and `require_admin` reads `current_user.role` off that row, a demotion
takes effect on the very next request. The test proves it: promote a
user, call the admin route (200), demote them, call it again with the
same unexpired token (403).

## Why PUT is a full replacement

`PUT /api/climbs/<id>` replaces the record's mutable fields. Missing
`route_name` or `outcome` is a 400, and optional fields left out of
the body are set to null — it never merges with the old row. That is
honest about what PUT means, and it is also safer: if "absent quietly
meant null" were false and a client bug dropped a field, the old value
would silently survive and the client would believe the change landed.
The same validator function is used by POST and PUT — literally the
same function, not a copy — so "is this a valid climb" is defined in
exactly one place and the 400 body shape is identical for both.
`PUT /api/profile` works the same way, with one refinement: `{}` is a
400 (the field was not sent) but `{"display_name": null}` validly
clears the name, so "clear my name" is expressible at all.

## Why a second DELETE returns 404

`DELETE` returns 204 with no body, and a second `DELETE` of the same id
returns 404. The record is gone, so "not found" is the honest answer —
a second 204 would claim something was deleted when nothing was. This
is a deliberate choice, not an accident: the delete uses the same
scoped query (`WHERE id = ? AND user_id = ?`, checking the row count),
so a second delete and a delete of someone else's climb are
indistinguishable, exactly like the reads.

## Why register returns a token

Registration mints a token immediately (201 with `token` and
`expires_in`, 43200 seconds = 12 hours) so the client does not need a
follow-up login call to start using the API. The duplicate-email case
is a 409 that comes from catching the database `IntegrityError` on the
unique index — not from a SELECT-then-INSERT pre-check, which two
simultaneous signups could both pass. The database is the authority
on uniqueness; the code just translates its error into the right
status code.

## Why login collapses wrong-email and wrong-password into one 401

Both failures return 401 with the byte-identical message
"invalid email or password". If an unknown email returned a different
status or message than a wrong password, login would become an
account-enumeration oracle: anyone could probe which emails are
registered. When the email is not found, the code still runs a bcrypt
compare against a precomputed dummy hash, so a wrong-email attempt
costs the same time as a wrong-password attempt and timing does not
leak the difference either.

## Why JWT_SECRET is the one name, and why production fails fast

The secret is called `JWT_SECRET` in exactly two places: the config
class and `.env.example`. It is not called `SECRET_KEY`, because this
API is bearer-token-only — there are no Flask sessions — and a generic
name is how a deploy ends up signing tokens with a different secret
than the code expects while booting fine. In production the config
class leaves it `None` on purpose, and `production_overrides()` —
called only when production is actually selected, never at import —
raises `RuntimeError` listing the missing variables. A missing prod
secret must crash startup loudly; the alternative is silently signing
every token with a publicly-known dev fallback.

## Why migrations are not in the Dockerfile CMD

The Dockerfile runs 3 gunicorn workers. If `flask db upgrade` were in
the CMD, all three workers would try to migrate at once and race on
the `alembic_version` table. Migrations run once, before the app
starts: `docker compose run --rm web flask --app run.py db upgrade`
locally, and the Render Pre-Deploy Command on deploy. The same
reasoning is why the Dockerfile copies `requirements.txt` and runs
`pip install` *before* copying the code — a code edit then does not
invalidate the dependency layer — and why `USER appuser` runs the app
as a non-root user (uid 10001).

## Why there is no logout endpoint and no /api/users/<id>

Tokens are bearer tokens with no server session to destroy, so a
logout endpoint would be theatre — expiry (12h) plus re-login is the
honest model for v1. And a user collection would contradict the
ownership model: the whole API is built on "you can only ever see
your own records", so there is no endpoint that lists or reads other
users except the admin-only `GET /api/admin/users`, which exists for
administration, not for regular users.
