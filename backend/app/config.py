from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Relationship Tracker API"
    frontend_url: str = "http://localhost:5173"
    database_url: str | None = None
    session_secret: str

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_callback_url: str | None = None

    apple_client_id: str | None = None
    apple_team_id: str | None = None
    apple_key_id: str | None = None
    apple_private_key: str | None = None
    apple_callback_url: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-6-astra"

    model_config = SettingsConfigDict(
        env_file=(Path(__file__).resolve().parents[2] / ".env",
                  Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
