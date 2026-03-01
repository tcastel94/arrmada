"""SQLAlchemy async engine, session factory, and database helpers.

Supports both SQLite (aiosqlite) and PostgreSQL (asyncpg):
  - SQLite:    sqlite+aiosqlite:///./data/arrmada.db
  - PostgreSQL: postgresql+asyncpg://user:pass@host:5432/arrmada
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# ── Engine configuration ─────────────────────────────────────
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    # Ensure the data directory exists for SQLite
    _db_path = settings.DATABASE_URL.split("///")[-1] if "///" in settings.DATABASE_URL else None
    if _db_path:
        Path(_db_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL (or other async DBs)
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Check connection liveness
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables (used on first startup before Alembic is run)."""
    from app.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    await engine.dispose()
