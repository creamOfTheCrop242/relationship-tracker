from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    value = get_settings().database_url
    if not value:
        raise RuntimeError("DATABASE_URL is not configured")
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value.removeprefix("postgres://")
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value.removeprefix("postgresql://")
    return value


@lru_cache
def get_engine() -> Engine:
    return create_engine(database_url(), pool_pre_ping=True, connect_args={"connect_timeout": 5})


def get_db() -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=get_engine(), autoflush=False)
    with session_factory() as session:
        yield session
