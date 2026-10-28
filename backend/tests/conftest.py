"""Test configuration and fixtures."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncGenerator

import pytest

# Isolated data dir (JWT secret, password hash, Fernet key) — must be set
# BEFORE app.config is imported, so it never touches a real ./data.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="arrmada-test-")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app, limiter
from app.models import Base
from app.services import (
    artwork,
    auth_store,
    fully_kiosk,
    jellyfin,
    media_aggregator,
    translations,
    tv_priority,
)
from app.utils.cache import cache
from tests import fake_arr

TEST_PASSWORD = "test-password-123"

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def admin_password():
    """Every test starts from a claimed instance (password = TEST_PASSWORD)."""
    auth_store.set_password(TEST_PASSWORD)
    yield TEST_PASSWORD
    auth_store.clear_password()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test and drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Vide le cache mémoire global entre deux tests.

    Sans ça, un test qui lit `/api/media` sur une base vide met « 0 média »
    en cache 5 min… et le test suivant (avec un faux Radarr) le relit.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _clear_jellyfin_indexes():
    """Index Jellyfin (films par TMDB, séries par TVDB) : vides à chaque test."""
    jellyfin._movie_cache.clear()
    jellyfin._series_cache.clear()
    yield
    jellyfin._movie_cache.clear()
    jellyfin._series_cache.clear()


@pytest.fixture(autouse=True)
def _isolated_library_snapshot(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Dernière liste connue de la médiathèque : propre à chaque test, jamais dans data/.

    Sans ça, un test où Radarr ne répond pas relirait la liste d'un test précédent.
    """
    monkeypatch.setattr(media_aggregator, "SNAPSHOT_FILE", tmp_path / "library-snapshot.json")
    monkeypatch.setattr(media_aggregator, "_snapshots", None)
    media_aggregator._digests.clear()
    media_aggregator._status.clear()
    yield
    media_aggregator._digests.clear()
    media_aggregator._status.clear()


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = _override_get_db
# Tablette en mode kiosk (services/fully_kiosk.py) : même base que les tests
fully_kiosk.session_factory = TestSessionFactory
# Récupération des artworks en arrière-plan (services/artwork.py) : idem
artwork.session_factory = TestSessionFactory
# Synopsis français (services/translations.py) : idem
translations.session_factory = TestSessionFactory
# Gardien de priorité des demandes TV (services/tv_priority.py) : idem
tv_priority.session_factory = TestSessionFactory

# Le login est limité à 5 essais/minute (anti brute-force). Chaque test qui
# utilise `auth_headers` se reconnecte : sans ça, le 6e test prend un 429
# et tout ce qui suit échoue en cascade. On coupe le limiteur pour la suite.
limiter.enabled = False


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Get valid auth headers for protected endpoints."""
    resp = await client.post(
        "/api/auth/login",
        json={"password": TEST_PASSWORD},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def fake_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coupe Internet : seuls le faux Radarr et le faux Sonarr répondent."""
    fake_arr.install(monkeypatch)


@pytest_asyncio.fixture
async def arr_stack(
    client: AsyncClient, auth_headers: dict[str, str], fake_network: None
) -> dict[str, str]:
    """Déclare un Radarr et un Sonarr (simulés) via l'API, comme un utilisateur.

    Renvoie les en-têtes d'authentification pour enchaîner les appels.
    """
    for svc in (
        {"name": "Radarr", "type": "radarr", "url": fake_arr.RADARR_URL, "api_key": "r-key"},
        {"name": "Sonarr", "type": "sonarr", "url": fake_arr.SONARR_URL, "api_key": "s-key"},
    ):
        resp = await client.post("/api/services", json=svc, headers=auth_headers)
        assert resp.status_code == 201, resp.text
    return auth_headers
