# FastAPI backend

The backend runs as a separate FastAPI service. Netlify continues to host the React frontend; Heroku will host this API and its PostgreSQL database.

## Local development

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

The health endpoint is available at `http://localhost:8000/api/health`.

## Heroku

Create a Heroku app and attach Heroku Postgres. Heroku supplies `DATABASE_URL`; add `FRONTEND_URL` and `SESSION_SECRET` as config vars. The `backend/Procfile` starts the API with Heroku's `PORT` when the backend subtree is deployed.

Authentication and relationship data endpoints will move from the temporary Netlify Functions into this service in the next backend step.
