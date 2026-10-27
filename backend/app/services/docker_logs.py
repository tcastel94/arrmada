"""Aggregated Docker container logs via the Docker Engine API (unix socket).

The Unraid GraphQL API doesn't expose container logs, so we read them straight
from the Docker daemon over ``/var/run/docker.sock`` (mounted read-only into the
backend). httpx can speak HTTP over a unix socket, so no extra dependency is
needed. We only pull logs for the containers that match registered services
(same filtered set as the Docker page), classify each line's level, merge them
and return the most recent lines across all containers.
"""

from __future__ import annotations

import asyncio
import re
from collections import Counter
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file_manager import get_docker_containers
from app.services.llm import LLMUnavailableError, chat_json, parse_json_object
from app.utils.logger import get_logger

logger = get_logger(__name__)

DOCKER_SOCK = "/var/run/docker.sock"

# "<rfc3339-ts> <rest of line>" — docker --timestamps prepends a UTC timestamp.
_TS_RE = re.compile(r"^(\S+)\s(.*)$")
# App loggers repeat their own timestamp inside the message — drop the leading one.
_INNER_TS_RE = re.compile(r"^\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d[.,]\d+\s*")
# binhex containers wrap everything through supervisord; these lines are noise.
_SUPERVISOR_RE = re.compile(r"DEBG '.*?' std(?:out|err) output:\s*$")

# Level detection covers the formats of the *arr stack:
#   Sonarr/Radarr/Prowlarr [Error]/[Warn]/[Info]   Jellyfin [ERR]/[WRN]/[INF]/[FTL]
#   Bazarr (python)  ERROR / WARNING / INFO         SABnzbd ::ERROR::/::WARNING::/::INFO::
_ERROR_RE = re.compile(
    r"\[(?:error|err|ftl|fatal|crit(?:ical)?)\]|::(?:error|critical)::|\s(?:ERROR|CRITICAL|FATAL)\s",
    re.IGNORECASE,
)
_WARN_RE = re.compile(r"\[(?:warn(?:ing)?|wrn)\]|::warning::|\sWARNING\s", re.IGNORECASE)
_INFO_RE = re.compile(r"\[(?:info|inf)\]|::info::|\sINFO\s", re.IGNORECASE)


def _classify(line: str) -> str:
    if _ERROR_RE.search(line):
        return "error"
    if _WARN_RE.search(line):
        return "warning"
    if _INFO_RE.search(line):
        return "info"
    return "other"


def _demux(raw: bytes) -> bytes:
    """Demultiplex a non-TTY Docker log stream (8-byte frame headers).

    Each frame: [stream(1)][0,0,0][size(4, big-endian)][payload]. If the bytes
    aren't framed (TTY containers), return them untouched.
    """
    out = bytearray()
    i, n = 0, len(raw)
    while i + 8 <= n:
        if raw[i] not in (0, 1, 2):
            return raw
        size = int.from_bytes(raw[i + 4 : i + 8], "big")
        i += 8
        out += raw[i : i + size]
        i += size
    return bytes(out)


async def _fetch_container_logs(client: httpx.AsyncClient, name: str, tail: int) -> bytes:
    r = await client.get(
        f"/containers/{name}/logs",
        params={"stdout": 1, "stderr": 1, "tail": tail, "timestamps": 1},
    )
    r.raise_for_status()
    return r.content


async def get_aggregated_logs(
    db: AsyncSession, tail: int = 60, limit: int = 200
) -> list[dict[str, Any]]:
    """Return recent log lines merged across the registered-service containers."""
    containers = await get_docker_containers(db)
    if not containers:
        return []

    transport = httpx.AsyncHTTPTransport(uds=DOCKER_SOCK)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://docker", timeout=10
    ) as client:
        results = await asyncio.gather(
            *[_fetch_container_logs(client, c["name"], tail) for c in containers],
            return_exceptions=True,
        )

    entries: list[dict[str, Any]] = []
    for c, raw in zip(containers, results, strict=True):  # même longueur (gather)
        if isinstance(raw, Exception):
            logger.warning("Docker logs fetch failed for %s: %s", c["name"], raw)
            continue
        text = _demux(raw).decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.rstrip()
            if not line:
                continue
            m = _TS_RE.match(line)
            if not m:
                continue
            ts, msg = m.group(1), m.group(2).rstrip()
            if not msg or _SUPERVISOR_RE.search(msg):
                continue
            msg = _INNER_TS_RE.sub("", msg).rstrip()
            if not msg:
                continue
            entries.append(
                {
                    "ts": ts,
                    "time": ts[11:19] if len(ts) >= 19 else ts,
                    "container": c["name"],
                    "service": c.get("service_name") or c["name"],
                    "level": _classify(msg),
                    "message": msg,
                }
            )

    entries.sort(key=lambda e: e["ts"], reverse=True)
    return entries[:limit]


ANALYZE_SYSTEM_PROMPT = """Tu es un expert d'un homelab média basé sur la suite *arr \
(Sonarr, Radarr, Prowlarr, SABnzbd, Bazarr, Jellyfin) tournant sur un NAS Unraid.
On te fournit un extrait dédupliqué des logs récents (erreurs et avertissements) de ces conteneurs.
Analyse-les, regroupe les problèmes DISTINCTS (surtout pas ligne par ligne), et pour chacun
propose une résolution concrète et actionnable.

Réponds UNIQUEMENT avec un objet JSON valide (aucun markdown, aucun texte autour) :
{
  "summary": "synthèse générale en 1-2 phrases",
  "problems": [
    {
      "title": "titre court du problème",
      "severity": "error" | "warning",
      "services": ["Sonarr", ...],
      "cause": "cause probable, expliquée simplement",
      "solution": "étapes concrètes de résolution",
      "occurrences": 12
    }
  ]
}
Limite-toi aux 6 problèmes les plus importants.
Classe les problèmes du plus critique au moins critique. Concret, technique mais concis. En français."""


async def analyze_logs(db: AsyncSession, tail: int = 150) -> dict[str, Any]:
    """Send recent error/warning log lines to the LLM for problem analysis.

    Uses the local Ollama on the NAS first, falls back to OpenRouter.
    """
    entries = await get_aggregated_logs(db, tail=tail, limit=2000)
    signal = [e for e in entries if e["level"] in ("error", "warning")]
    if not signal:
        return {
            "summary": "Aucune erreur ni avertissement récent dans les logs.",
            "problems": [],
            "ai_available": True,
            "analyzed_lines": 0,
        }

    # Dedupe by (service, message) and count occurrences — collapses the many
    # near-identical repeats (e.g. one "Import failed" per file) into one signal.
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for e in signal:
        key = (e["service"], e["message"])
        g = groups.get(key)
        if g is None:
            groups[key] = {
                "service": e["service"],
                "level": e["level"],
                "message": e["message"],
                "count": 1,
            }
        else:
            g["count"] += 1
    digest = sorted(groups.values(), key=lambda g: g["count"], reverse=True)[:80]
    log_text = "\n".join(
        f"[{g['service']}/{g['level']}] (x{g['count']}) {g['message'][:300]}" for g in digest
    )
    user_msg = f"Logs (erreurs/avertissements dédupliqués) :\n\n{log_text}"

    try:
        content, engine_used = await chat_json(
            ANALYZE_SYSTEM_PROMPT,
            user_msg,
            temperature=0.2,
            ollama_max_tokens=1000,
            ollama_timeout=180,
            openrouter_max_tokens=1600,
            openrouter_timeout=45,
            purpose="Analyse IA",
        )
    except LLMUnavailableError as exc:
        return {
            "error": str(exc),
            # Aucun moteur n'a répondu : l'interface affiche comment en configurer un.
            "ai_available": False,
        }

    try:
        result = parse_json_object(content)
    except Exception as exc:  # noqa: BLE001
        logger.error("Parsing de la réponse IA échoué: %s", exc)
        return {"error": "Réponse IA illisible", "ai_available": True, "engine": engine_used}

    result["ai_available"] = True
    result["engine"] = engine_used
    result["analyzed_lines"] = len(signal)
    result["level_counts"] = dict(Counter(e["level"] for e in signal))
    return result
