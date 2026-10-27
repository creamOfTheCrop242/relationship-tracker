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

Run `npm run dev` alongside FastAPI. Vite proxies `/api` requests to port 8000. Sign-in requires configured provider credentials and registered callbacks; AI reflection storage requires migration `0006_ai_reflections`.

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

`GET /api/events?limit=50&offset=0` returns newest entries first. It accepts optional `q`, `category`, `person`, `occurred_from`, and exclusive `occurred_before` filters; filters can be combined and pagination applies to the filtered results. Search covers the description, notes, mood, impact, and category-specific details. `POST /api/events`, `PUT /api/events/{id}`, and `DELETE /api/events/{id}` create, edit, and remove entries. Every route requires an unexpired session. Mutations require an Origin header matching `FRONTEND_URL`. Ownership comes from the session and cannot be supplied by the client.

Migration `0002_events` creates the relationship and event tables. Deploy the backend and verify readiness before merging the frontend change. The tests cover validation, timezone conversion, pagination, cascading deletion, and isolation between users. Full browser acceptance: save an entry, refresh, edit it, cancel a deletion, confirm deletion, and verify a failed request preserves form input.

Migration `0003_event_details` adds a JSONB object for category-specific values. The API validates the allowed shape for each category, including 1–5 ratings, enumerated selections, optional booleans, text limits, and childcare duration. Existing events receive an empty details object and remain readable.

Migration `0004_relationship_needs` adds `relationship_needs` and `need_updates`. `GET /api/needs` lists active needs and accepts `include_archived=true`. `POST /api/needs`, `PUT /api/needs/{id}`, and `PATCH /api/needs/{id}/archive` create, edit, archive, or restore a need. Nested `/api/needs/{id}/updates` routes create, edit, and delete dated history. The API validates cadence combinations, partner confirmation, statuses, satisfaction ratings, ownership, and text limits.

Migration `0005_need_integrity` adds database constraints for valid cadence and partner-confirmation combinations.

`GET /api/dashboard` returns the signed-in user's latest event in each dashboard category, latest conflict that records someone as upset, five recent events, and active need summaries. Need summaries flag a latest satisfaction rating of 1–2, flag records with no update in the last 14 days, and calculate a trend after four updates by comparing the latest two satisfaction ratings with the previous two. The route uses session ownership for every event and need query.

## AI reflections

Migration `0006_ai_reflections` adds the global per-user AI setting, IANA timezone, and persisted `relationship_summaries`. Configure `OPENAI_API_KEY` only in the backend environment and optionally set `OPENAI_MODEL` (default `gpt-6-astra`). The implementation uses the Responses API with Pydantic Structured Outputs and `store=False`, following the [official OpenAI Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

`GET` and `PUT /api/analysis/settings` read and update the global opt-in. `POST /api/reflections/generate` manually generates or regenerates a daily, weekly, monthly, or yearly period. `GET /api/reflections` lists saved results, and `DELETE /api/reflections/{id}` removes one. All routes require an unexpired user session and apply ownership from that session. Fewer than two eligible records creates a scoreless coverage report without calling OpenAI.

`POST /api/analysis/advice` answers one question using up to 30 of the signed-in user's recent events and 30 recent need updates. It requires the same global AI opt-in, uses structured output with OpenAI storage disabled, and does not persist the question or response locally.

## Account privacy

`GET /api/account/export` returns a downloadable JSON export containing the signed-in user's profile, connected providers, relationship, events, needs and updates, and saved reflections. Session records and token hashes are excluded. `DELETE /api/account` requires `{"confirmation":"DELETE"}`, permanently deletes the user and all related records through database cascades, and clears the session cookie. Both endpoints require a current session, return `Cache-Control: no-store`, and account deletion requires the configured frontend origin.

For scheduled generation, configure a trusted hourly Heroku Scheduler job:

```bash
python -m app.reflection_jobs
```

The job checks each enabled user's local timezone and generates a completed daily period after 3:00 AM. It also generates the completed week on Monday, month on the first day, and year on January 1. Existing period rows prevent duplicate scheduled calls.
