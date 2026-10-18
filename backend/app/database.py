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


# Colonnes ajoutées à une table existante : `create_all` crée les tables
# manquantes mais ne touche jamais une table déjà là. Comme un script de
# mise à jour de schéma idempotent : on ajoute la colonne si elle manque.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("devices", "kind", "VARCHAR(20) NOT NULL DEFAULT 'tv'"),  # écran d'appoint
    # Tablette en mode kiosk pendant un média (Fully Kiosk Remote Admin)
    ("devices", "kiosk_control", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("devices", "kiosk_host", "VARCHAR(255)"),
    ("devices", "kiosk_port", "INTEGER NOT NULL DEFAULT 2323"),
    ("devices", "kiosk_password", "VARCHAR(500)"),
    # Artworks : toutes les images d'un titre (galerie de l'onglet Artworks)
    ("media_artwork", "gallery", "JSON"),
    ("media_artwork", "gallery_count", "INTEGER NOT NULL DEFAULT 0"),
)


def add_missing_columns(sync_conn) -> list[str]:
    """Ajoute les colonnes de `_ADDED_COLUMNS` absentes ; renvoie celles ajoutées."""
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    added = []
    for table, column, ddl in _ADDED_COLUMNS:
        if table not in tables:
            continue  # créée à l'instant par create_all, déjà complète
        existing = {col["name"] for col in inspector.get_columns(table)}
        if column not in existing:
            sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            added.append(f"{table}.{column}")
    return added


async def init_db() -> None:
    """Create all tables (used on first startup before Alembic is run)."""
    from app.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(add_missing_columns)


async def close_db() -> None:
    """Dispose of the engine connection pool."""
    await engine.dispose()
