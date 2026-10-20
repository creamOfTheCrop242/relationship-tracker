# FastAPI backend

Netlify hosts the React frontend. The FastAPI service and its PostgreSQL database are intended for Heroku. Authentication runs in FastAPI; see `AUTH-SETUP.md` for provider configuration and frontend proxy routing.

## Local development

Use Python 3.12 and PostgreSQL 14 or newer. From the repository root:

```bash
python3.12 -m venv .venv-backend
source .venv-backend/bin/activate
pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
createdb relationship_tracker
```

Edit `backend/.env` to set `DATABASE_URL` to your local Postgres connection and set a random `SESSION_SECRET` (generate with `openssl rand -hex 32`). Adjust the example database username/password for your local installation. Do not overwrite an existing environment file.

Configuration reads the root `.env`, then `backend/.env`; process environment variables take precedence over both. Neither environment file is committed.

Apply the schema and start the backend:

```bash
alembic -c backend/alembic.ini upgrade head
uvicorn backend.app.main:app --reload --port 8000
```

- `GET /api/health`: service liveness, independent of the database.
- `GET /api/ready`: database connectivity and required account tables; returns 503 if unavailable or not migrated.
- `http://localhost:8000/docs`: API documentation.

Run `npm run dev` alongside FastAPI. Vite proxies `/api` requests to port 8000. Sign-in requires configured provider credentials and registered callbacks; entry storage requires migration `0002_events`.

## Database migrations

The initial migration creates `users`, `auth_accounts`, and `sessions`, including unique provider identities, unique session token hashes, and cascading deletion of a user's accounts and sessions. Session rows store hashes, not raw tokens.

```bash
alembic -c backend/alembic.ini current
alembic -c backend/alembic.ini check
alembic -c backend/alembic.ini revision --autogenerate -m "describe the change"
```

Review generated migrations before applying them. Use these migrations with a fresh FastAPI database. They do not transfer existing Netlify data; do not run the initial migration over existing Netlify tables or stamp them without comparing the schemas first.

## Tests

Create a separate test database and migrate it before running integration tests:

```bash
createdb relationship_tracker_test
DATABASE_URL=postgresql://localhost/relationship_tracker_test alembic -c backend/alembic.ini upgrade head
TEST_DATABASE_URL=postgresql://localhost/relationship_tracker_test python -m unittest discover -s backend/tests -v
```

Tests roll back their data. Without `TEST_DATABASE_URL`, database tests are skipped and health endpoint tests still run. `SESSION_SECRET` must be configured as for local development.

## Heroku

Deploy the `backend` directory as the app root, create a Heroku app, and attach Heroku Postgres. Heroku supplies `DATABASE_URL`; configure `FRONTEND_URL` and `SESSION_SECRET` as config vars. `backend/.python-version` selects Python 3.12.

The Procfile release command runs `alembic -c alembic.ini upgrade head` before starting the web process. No application code creates or modifies tables automatically. Verify `/api/ready` after deployment.

## Private journal endpoints

`GET /api/relationship` returns the current user's relationship (or null). `PUT /api/relationship` saves an optional partner name; the UI defaults it to “Partner”. `POST /api/events` also creates the default relationship automatically if needed.

`GET /api/events?limit=50&offset=0` returns newest entries first. `POST /api/events`, `PUT /api/events/{id}`, and `DELETE /api/events/{id}` create, edit, and remove entries. Every route requires an unexpired session. Mutations require an Origin header matching `FRONTEND_URL`. Ownership comes from the session and cannot be supplied by the client.

Migration `0002_events` creates the relationship and event tables. Deploy the backend and verify readiness before merging the frontend change. The tests cover validation, timezone conversion, pagination, cascading deletion, and isolation between users. Full browser acceptance: save an entry, refresh, edit it, cancel a deletion, confirm deletion, and verify a failed request preserves form input.
