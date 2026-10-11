"""Test configuration and fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import get_db
from app.main import app, limiter
from app.models import Base
from app.services import fully_kiosk
from app.utils.cache import cache
from tests import fake_arr

# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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
        json={"password": settings.ARRMADA_AUTH_SECRET},
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
