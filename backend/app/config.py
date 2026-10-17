from functools import lru_cache

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
