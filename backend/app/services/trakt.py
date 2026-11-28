"""Trakt : notes et lecture en direct, un compte par profil famille (ADR-022).

Ce que fait ArrMada sur Trakt, pour le profil qui regarde :
  - **lecture en direct** (« scrobble ») : la TV envoie déjà au serveur
    « lecture / pause / reprise / arrêt » pour la tablette du salon ; le
    serveur relaie à Trakt (start / pause / stop avec le % vu). Passé 80 %,
    Trakt marque le titre comme vu ;
  - **notes** : à la fin d'un film ou d'un épisode, la TV propose une note
    (5 étoiles, demi-étoiles = 1 à 10 sur Trakt) ; à la fin d'une saison ou de
    la série, une note de la saison / de la série.

Liaison d'un compte : « code d'appareil » (OAuth device flow). ArrMada demande
un code à Trakt, tu le tapes sur trakt.tv/activate, ArrMada récupère les
jetons. Rien à ouvrir sur Internet, pas d'adresse de retour à configurer.
Analogie : l'appairage d'une TV avec un code affiché à l'écran.

Jetons : chiffrés en base ; renouvelés tout seuls avant expiration (et une
fois de plus si Trakt répond 401).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import settings
from app.database import async_session_factory
from app.models.trakt_account import TraktAccount
from app.services.encryption import decrypt_api_key, encrypt_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Remplacée par les tests (base en mémoire), comme dans les autres services
# qui ouvrent leurs propres sessions hors d'une requête.
session_factory = async_session_factory

API = "https://api.trakt.tv"
REFRESH_MARGIN = timedelta(hours=6)  # renouvelé un peu avant l'expiration
TIMEOUT = 15
OOB_REDIRECT = "urn:ietf:wg:oauth:2.0:oob"
# Connexion (OAuth) : Trakt demande désormais l'hôte « auth » ; l'ancien hôte
# (celui des données) sert de repli s'il ne répond pas ou ne connaît pas la route.
AUTH = "https://auth.trakt.tv"

# Libellés des notes (ceux de Trakt, traduits) : affichés sous les étoiles
RATING_LABELS = {
    1: "Nul",
    2: "Très mauvais",
    3: "Mauvais",
    4: "Bof",
    5: "Moyen",
    6: "Correct",
    7: "Bien",
    8: "Très bien",
    9: "Excellent",
    10: "Chef-d'œuvre",
}


class TraktError(RuntimeError):
    """Trakt a refusé ou n'a pas répondu ; le message est lisible tel quel."""


def configured() -> bool:
    """Le Client ID suffit : depuis octobre 2026, les applications Trakt n'ont
    plus de « client secret » (la liaison par code d'appareil n'en a pas besoin)."""
    return bool(settings.TRAKT_CLIENT_ID)


def _with_secret(body: dict[str, Any]) -> dict[str, Any]:
    """Ajoute le secret aux échanges de connexion, seulement pour une ancienne application qui en a un."""
    if settings.TRAKT_CLIENT_SECRET:
        return {**body, "client_secret": settings.TRAKT_CLIENT_SECRET}
    return body


def profile_key(profile_id: int | None) -> int:
    """Profil du jeton (None = « Famille ») → clé de stockage (0 = « Famille »)."""
    return int(profile_id or 0)


def _headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": settings.TRAKT_CLIENT_ID,
        # Trakt (derrière Cloudflare) refuse les requêtes sans User-Agent explicite
        "User-Agent": f"ArrMada/{__version__}",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _post(path: str, payload: dict[str, Any], token: str | None = None) -> httpx.Response:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        if path.startswith("/oauth/"):
            try:
                resp = await client.post(f"{AUTH}{path}", json=payload, headers=_headers(token))
                if resp.status_code != 404:
                    return resp
            except httpx.HTTPError as exc:
                logger.info("Trakt : %s injoignable (%s), repli sur %s", AUTH, exc, API)
        return await client.post(f"{API}{path}", json=payload, headers=_headers(token))


async def _get(path: str, token: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        return await client.get(f"{API}{path}", headers=_headers(token))


# ══════════════════════════════════════════════════════════════
# Comptes
# ══════════════════════════════════════════════════════════════


async def account(db: AsyncSession, profile_id: int | None) -> TraktAccount | None:
    key = profile_key(profile_id)
    return (
        (await db.execute(select(TraktAccount).where(TraktAccount.profile_key == key)))
        .scalars()
        .first()
    )


async def accounts(db: AsyncSession) -> dict[int, TraktAccount]:
    rows = (await db.execute(select(TraktAccount))).scalars().all()
    return {row.profile_key: row for row in rows}


def _expires(tokens: dict[str, Any]) -> datetime:
    created = tokens.get("created_at")
    start = datetime.fromtimestamp(int(created), UTC) if created else datetime.now(UTC)
    return start + timedelta(seconds=int(tokens.get("expires_in") or 86400))


async def _save_tokens(
    db: AsyncSession, key: int, tokens: dict[str, Any], username: str | None = None
) -> TraktAccount:
    row = (
        (await db.execute(select(TraktAccount).where(TraktAccount.profile_key == key)))
        .scalars()
        .first()
    )
    now = datetime.now(UTC)
    if row is None:
        row = TraktAccount(profile_key=key, linked_at=now)
        db.add(row)
    row.access_token = encrypt_api_key(tokens["access_token"])
    row.refresh_token = encrypt_api_key(tokens["refresh_token"])
    row.expires_at = _expires(tokens)
    if username is not None:
        row.username = username
    await db.commit()
    await db.refresh(row)
    return row


def _aware(value: datetime) -> datetime:
    # SQLite rend des dates sans fuseau : elles sont en UTC
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _refresh_body(refresh_token: str) -> dict[str, Any]:
    """Renouvellement : le jeton de renouvellement ne sert qu'une fois (le nouveau est gardé)."""
    body: dict[str, Any] = {
        "refresh_token": refresh_token,
        "client_id": settings.TRAKT_CLIENT_ID,
        "grant_type": "refresh_token",
    }
    if settings.TRAKT_CLIENT_SECRET:  # ancienne application : secret + adresse de retour
        body.update(client_secret=settings.TRAKT_CLIENT_SECRET, redirect_uri=OOB_REDIRECT)
    return body


async def _refresh(db: AsyncSession, row: TraktAccount) -> TraktAccount:
    resp = await _post(
        "/oauth/token",
        _refresh_body(decrypt_api_key(row.refresh_token)),
    )
    if resp.status_code != 200:
        raise TraktError(
            "Trakt a refusé le renouvellement de la connexion : relie à nouveau le compte "
            "dans Paramètres › Trakt"
        )
    return await _save_tokens(db, row.profile_key, resp.json())


async def _token(db: AsyncSession, row: TraktAccount) -> str:
    if _aware(row.expires_at) - datetime.now(UTC) < REFRESH_MARGIN:
        row = await _refresh(db, row)
    return decrypt_api_key(row.access_token)


async def _call(
    db: AsyncSession, row: TraktAccount, path: str, payload: dict[str, Any]
) -> httpx.Response:
    """POST authentifié ; un 401 (jeton révoqué côté Trakt) → un renouvellement, un essai."""
    resp = await _post(path, payload, await _token(db, row))
    if resp.status_code == 401:
        row = await _refresh(db, row)
        resp = await _post(path, payload, decrypt_api_key(row.access_token))
    return resp


# ══════════════════════════════════════════════════════════════
# Liaison par code d'appareil
# ══════════════════════════════════════════════════════════════


async def start_link() -> dict[str, Any]:
    """Code à taper sur trakt.tv/activate : {device_code, user_code, verification_url, …}."""
    if not configured():
        raise TraktError("Trakt n'est pas configuré : TRAKT_CLIENT_ID manquant dans le .env")
    resp = await _post("/oauth/device/code", {"client_id": settings.TRAKT_CLIENT_ID})
    if resp.status_code != 200:
        raise TraktError(f"Trakt refuse de donner un code (HTTP {resp.status_code})")
    data = resp.json()
    return {
        "device_code": data["device_code"],
        "user_code": data["user_code"],
        "verification_url": data.get("verification_url") or "https://trakt.tv/activate",
        "expires_in": int(data.get("expires_in") or 600),
        "interval": int(data.get("interval") or 5),
    }


# Réponses de Trakt pendant l'attente du code (documentation de l'API)
_POLL_STATES = {
    400: "pending",  # pas encore tapé
    429: "pending",  # on interroge trop vite : on réessaiera
    404: "invalid",
    409: "used",
    410: "expired",
    418: "denied",
}


async def poll_link(db: AsyncSession, profile_id: int | None, device_code: str) -> dict[str, Any]:
    """Le code a-t-il été tapé ? {status: pending|linked|expired|denied|…, username?}."""
    resp = await _post(
        "/oauth/device/token",
        _with_secret({"code": device_code, "client_id": settings.TRAKT_CLIENT_ID}),
    )
    if resp.status_code != 200:
        return {"status": _POLL_STATES.get(resp.status_code, "error")}
    tokens = resp.json()
    username = ""
    try:
        me = await _get("/users/settings", tokens["access_token"])
        if me.status_code == 200:
            user = me.json().get("user") or {}
            username = user.get("username") or user.get("name") or ""
    except httpx.HTTPError:
        pass  # le nom n'est qu'un affichage : la liaison est faite
    await _save_tokens(db, profile_key(profile_id), tokens, username)
    return {"status": "linked", "username": username}


async def unlink(db: AsyncSession, profile_id: int | None) -> bool:
    row = await account(db, profile_id)
    if row is None:
        return False
    try:  # révoque le jeton chez Trakt (au mieux : on délie de toute façon)
        await _post(
            "/oauth/revoke",
            _with_secret(
                {"token": decrypt_api_key(row.access_token), "client_id": settings.TRAKT_CLIENT_ID}
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Trakt : révocation impossible (%s), compte délié quand même", exc)
    await db.delete(row)
    await db.commit()
    return True


# ══════════════════════════════════════════════════════════════
# Identité d'un titre pour Trakt
# ══════════════════════════════════════════════════════════════


def media_body(
    kind: str,
    *,
    tmdb_id: int | None = None,
    tvdb_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
) -> dict[str, Any] | None:
    """Corps d'un scrobble : {movie: …} ou {show: …, episode: …} (pur, testé)."""
    if kind == "movie" and tmdb_id:
        return {"movie": {"ids": {"tmdb": int(tmdb_id)}}}
    if kind == "episode" and tvdb_id and season is not None and episode:
        return {
            "show": {"ids": {"tvdb": int(tvdb_id)}},
            "episode": {"season": int(season), "number": int(episode)},
        }
    return None


def rating_body(
    kind: str,
    rating: int,
    *,
    tmdb_id: int | None = None,
    tvdb_id: int | None = None,
    season: int | None = None,
    episode: int | None = None,
) -> dict[str, Any] | None:
    """Corps de /sync/ratings pour un film, un épisode, une saison ou une série (pur, testé)."""
    rated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if kind == "movie" and tmdb_id:
        return {"movies": [{"ids": {"tmdb": int(tmdb_id)}, "rating": rating, "rated_at": rated_at}]}
    if not tvdb_id:
        return None
    show: dict[str, Any] = {"ids": {"tvdb": int(tvdb_id)}}
    if kind == "show":
        show.update(rating=rating, rated_at=rated_at)
    elif kind == "season" and season is not None:
        show["seasons"] = [{"number": int(season), "rating": rating, "rated_at": rated_at}]
    elif kind == "episode" and season is not None and episode:
        show["seasons"] = [
            {
                "number": int(season),
                "episodes": [{"number": int(episode), "rating": rating, "rated_at": rated_at}],
            }
        ]
    else:
        return None
    return {"shows": [show]}


# ══════════════════════════════════════════════════════════════
# Notes et lecture en direct
# ══════════════════════════════════════════════════════════════


async def rate(db: AsyncSession, profile_id: int | None, kind: str, rating: int, **ids: Any) -> str:
    """Envoie une note (1 à 10). Renvoie le message à afficher sur la TV."""
    row = await account(db, profile_id)
    if row is None:
        raise TraktError("Aucun compte Trakt relié à ce profil")
    if not 1 <= int(rating) <= 10:
        raise TraktError("Note hors échelle (1 à 10)")
    body = rating_body(kind, int(rating), **ids)
    if body is None:
        raise TraktError("Titre non reconnu pour Trakt")
    resp = await _call(db, row, "/sync/ratings", body)
    if resp.status_code not in (200, 201):
        raise TraktError(f"Trakt a refusé la note (HTTP {resp.status_code})")
    added = resp.json().get("added") or {}
    if not any(added.values()):
        raise TraktError("Trakt ne connaît pas ce titre : note non enregistrée")
    stars = rating / 2
    shown = f"{stars:g}".replace(".", ",")
    return f"Noté {shown} ★ sur Trakt ({RATING_LABELS[int(rating)]})"


# Événements de la TV (même flux que la tablette du salon) → action Trakt
SCROBBLE_ACTIONS = {"play": "start", "resume": "start", "pause": "pause", "stop": "stop"}


def scrobble_plan(data: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """Événement reçu de la TV → (action Trakt, corps) ; None : rien à envoyer (pur, testé)."""
    action = SCROBBLE_ACTIONS.get(str(data.get("event") or ""))
    if action is None:
        return None  # « progress » : Trakt calcule seul l'avancement entre start et stop
    body = media_body(
        str(data.get("media_type") or ""),
        tmdb_id=_int(data.get("tmdb_id")),
        tvdb_id=_int(data.get("tvdb_id")),
        season=_int(data.get("season")),
        episode=_int(data.get("episode")),
    )
    if body is None:
        return None  # vidéo maison, titre sans identifiant : Trakt ne le connaît pas
    progress = _float(data.get("percentage"))
    body["progress"] = round(max(0.0, min(100.0, progress)), 2)
    return action, body


async def scrobble(db: AsyncSession, profile_id: int | None, data: dict[str, Any]) -> str | None:
    """Relaie un événement de lecture au compte Trakt du profil. Renvoie l'action faite."""
    if not configured():
        return None
    plan = scrobble_plan(data)
    if plan is None:
        return None
    row = await account(db, profile_id)
    if row is None:
        return None
    action, body = plan
    resp = await _call(db, row, f"/scrobble/{action}", body)
    # 409 : déjà marqué vu il y a peu (deux « stop » rapprochés) — pas une erreur
    if resp.status_code not in (200, 201, 409):
        logger.info("Trakt : scrobble %s refusé (HTTP %s)", action, resp.status_code)
        return None
    return action


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ══════════════════════════════════════════════════════════════
# Quelles notes proposer à la fin d'un épisode
# ══════════════════════════════════════════════════════════════


def rating_steps(
    episodes: list[dict[str, Any]], season: int, episode: int, series_ended: bool
) -> list[str]:
    """« episode », puis « season » (dernier épisode de la saison), puis « show »
    (dernier épisode de la dernière saison d'une série terminée). Pur, testé.

    Les épisodes spéciaux (saison 0) ne déclenchent que leur propre note.
    """
    steps = ["episode"]
    if season <= 0:
        return steps
    in_season = [
        int(e.get("episodeNumber") or 0)
        for e in episodes
        if int(e.get("seasonNumber") or 0) == season
    ]
    if not in_season or episode < max(in_season):
        return steps
    steps.append("season")
    seasons = [
        int(e.get("seasonNumber") or 0) for e in episodes if int(e.get("seasonNumber") or 0) > 0
    ]
    if series_ended and seasons and season >= max(seasons):
        steps.append("show")
    return steps


async def scrobble_in_background(profile_id: int | None, data: dict[str, Any]) -> None:
    """Appelé par /api/kodi/scrobble sans faire attendre la TV ; une erreur ne remonte jamais."""
    if not configured():
        return
    try:
        async with session_factory() as db:
            await scrobble(db, profile_id, data)
    except Exception as exc:  # noqa: BLE001 : Trakt injoignable, compte délié…
        logger.info("Trakt : scrobble non transmis (%s)", exc)
