"""Client Deluge (interface web, JSON-RPC) — vitesse, sources et pairs d'un torrent.

Radarr / Sonarr connaissent la file (titre, taille, temps restant) mais pas
ce qui se passe dans le client torrent : vitesse, seeders, pairs, ratio,
tracker. Ces infos sont lues directement dans Deluge, par son interface web
(port 8112 par défaut), comme le ferait le navigateur :

  1. POST /json {"method": "auth.login", "params": ["<mot de passe>"]} → cookie de session ;
  2. si l'interface web n'est reliée à aucun démon : web.get_hosts + web.connect ;
  3. core.get_torrents_status({"id": [hash…]}, [champs]).

Le « mot de passe » de l'interface web est rangé dans le champ « clé API »
du service (chiffré en base comme les autres clés). Lecture seule : ArrMada
ne met jamais en pause ni ne supprime un torrent.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.services.arr_client import ArrBaseClient, HealthStatus
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Champs demandés pour chaque torrent (noms de Deluge)
TORRENT_FIELDS = [
    "name", "state", "progress", "download_payload_rate", "upload_payload_rate",
    "num_seeds", "total_seeds", "num_peers", "total_peers", "eta", "ratio",
    "total_size", "total_done", "tracker_host", "time_added",
]  # fmt: skip


class DelugeError(RuntimeError):
    """Refus de Deluge (mot de passe, démon déconnecté, erreur RPC)."""


class DelugeClient(ArrBaseClient):
    """Client de l'interface web de Deluge (JSON-RPC sur /json)."""

    API_PREFIX: str = ""

    def __init__(self, url: str, api_key: str, *, timeout: int = 10) -> None:
        super().__init__(url, api_key, timeout=timeout)
        self._request_id = 0
        self._logged_in = False

    @property
    def client(self) -> httpx.AsyncClient:
        """Client HTTP sans en-tête X-Api-Key ; garde le cookie de session de Deluge."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def _rpc(self, method: str, *params: Any) -> Any:
        self._request_id += 1
        resp = await self.client.post(
            "/json", json={"method": method, "params": list(params), "id": self._request_id}
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("error"):
            error = body["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise DelugeError(f"Deluge : {message}")
        return body.get("result")

    async def login(self) -> None:
        """Ouvre la session, et relie l'interface web au démon si besoin."""
        if self._logged_in:
            return
        if not await self._rpc("auth.login", self.api_key):
            raise DelugeError("Deluge refuse le mot de passe de l'interface web")
        if not await self._rpc("web.connected"):
            hosts = await self._rpc("web.get_hosts") or []
            if not hosts:
                raise DelugeError("Deluge : aucun démon configuré dans l'interface web")
            await self._rpc("web.connect", hosts[0][0])
        self._logged_in = True

    async def torrents(self, hashes: list[str]) -> dict[str, dict[str, Any]]:
        """{hash en minuscules → état} des torrents demandés (absents : ignorés)."""
        wanted = [h.lower() for h in hashes if h]
        if not wanted:
            return {}
        await self.login()
        result = await self._rpc("core.get_torrents_status", {"id": wanted}, TORRENT_FIELDS)
        return {str(k).lower(): v for k, v in (result or {}).items() if isinstance(v, dict)}

    async def health_check(self) -> HealthStatus:
        start = time.monotonic()
        try:
            await self.login()
            version = None
            try:
                info = await self._rpc("daemon.info")
                version = str(info) if info else None
            except Exception:  # version facultative (ancienne interface web)
                version = None
            return HealthStatus(
                status="online", latency_ms=int((time.monotonic() - start) * 1000), version=version
            )
        except httpx.TimeoutException:
            return HealthStatus(
                status="offline", latency_ms=int((time.monotonic() - start) * 1000), error="Timeout"
            )
        except Exception as exc:
            return HealthStatus(
                status="offline", latency_ms=int((time.monotonic() - start) * 1000), error=str(exc)
            )


def torrent_view(status: dict[str, Any]) -> dict[str, Any]:
    """État Deluge → champs affichés par la tablette (unités : octets/s, secondes)."""

    def num(key: str) -> float:
        try:
            return float(status.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0

    eta = int(num("eta"))
    return {
        "state": str(status.get("state") or ""),  # Downloading, Seeding, Paused, Queued…
        "download_speed": int(num("download_payload_rate")),
        "upload_speed": int(num("upload_payload_rate")),
        "seeds": int(num("num_seeds")),
        "seeds_total": int(num("total_seeds")),
        "peers": int(num("num_peers")),
        "peers_total": int(num("total_peers")),
        "eta_seconds": eta if eta > 0 else None,
        "ratio": round(num("ratio"), 2) if num("ratio") >= 0 else None,
        "tracker": str(status.get("tracker_host") or ""),
        "added_at": int(num("time_added")) or None,
    }
