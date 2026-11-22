"""Фабрика движков SQLAlchemy: SQLite для тестов/разработки, PostgreSQL для прогонов."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

SQLITE_TEST = "sqlite+aiosqlite://"


def make_engine(url: str, *, echo: bool = False) -> Engine:
    """url: 'postgresql+asyncpg://...' или 'sqlite+aiosqlite:///path.db'."""
    if url.startswith("sqlite"):
        return create_engine(url, echo=echo, future=True)
    return create_engine(url, echo=echo, future=True, pool_pre_ping=True)


def is_postgres(engine: Engine) -> bool:
    return engine.dialect.name == "postgresql"
