from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .db import get_engine
from .auth import router as auth_router
from .journal import router as journal_router
from .needs import router as needs_router
from .dashboard import router as dashboard_router
from .reflections import router as reflections_router

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(auth_router)
app.include_router(journal_router)
app.include_router(needs_router)
app.include_router(dashboard_router)
app.include_router(reflections_router)


@app.exception_handler(SQLAlchemyError)
def database_error(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"}, headers={"Cache-Control": "no-store"})


@app.get("/")
def index():
    return {"service": settings.app_name, "docs": "/docs", "health": "/api/health", "ready": "/api/ready"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "relationship-tracker-api"}


@app.get("/api/ready")
def ready():
    try:
        with get_engine().connect() as connection:
            # Also checks that the initial migration has been applied.
            for table in ("users", "auth_accounts", "sessions", "relationships", "events", "relationship_needs", "need_updates", "relationship_summaries"):
                connection.execute(text(f"SELECT 1 FROM {table} LIMIT 0"))
        return {"status": "ok", "database": "ready"}
    except (SQLAlchemyError, RuntimeError):
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "not_ready"})
