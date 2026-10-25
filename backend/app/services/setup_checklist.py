"""« Ce qu'il te reste à faire » : the guided checklist shown after setup.

An installer can generate keys and wire apps together, but some steps need
the user: adding indexers in Prowlarr, a Usenet provider in SABnzbd… Each
item below is CHECKED against the real app (not just ticked by hand), so the
wizard can say what is done and lead the user to what is left, with a plain
explanation and a direct link.

Statuses: ``done`` · ``todo`` (the user has something to do) · ``error``
(the app did not answer: shown, but never blocks).
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.services.encryption import decrypt_api_key
from app.services.jellyfin import auth_header as jellyfin_auth
from app.services.stack.wiring import load_stack_metadata
from app.utils.logger import get_logger

logger = get_logger(__name__)

TIMEOUT = 5.0
LABELS = {
    "sonarr": "Sonarr",
    "radarr": "Radarr",
    "prowlarr": "Prowlarr",
    "sabnzbd": "SABnzbd",
    "jellyfin": "Jellyfin",
    "deluge": "Deluge",
    "qbittorrent": "qBittorrent",
    "bazarr": "Bazarr",
}


def _item(
    item_id: str,
    title: str,
    why: str,
    *,
    status: str,
    detail: str = "",
    how: str = "",
    service: Service | None = None,
    path: str = "",
) -> dict[str, Any]:
    """One checklist line. ``link`` points to the app's own page to act."""
    link = None
    if service is not None:
        base = service.url.rstrip("/")
        link = {"url": f"{base}{path}", "label": f"Ouvrir {LABELS.get(service.type, service.name)}"}
    return {
        "id": item_id,
        "title": title,
        "why": why,
        "how": how,
        "status": status,
        "detail": detail,
        "service_type": service.type if service else None,
        "link": link,
    }


async def _get_json(client: httpx.AsyncClient, url: str, **kwargs: Any) -> Any:
    resp = await client.get(url, timeout=TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.json()


def _key(service: Service) -> str:
    try:
        return decrypt_api_key(service.api_key)
    except Exception:  # noqa: BLE001 — unreadable key: the check reports an error
        return ""


async def _arr_count(client: httpx.AsyncClient, svc: Service, path: str) -> int:
    version = "v1" if svc.type == "prowlarr" else "v3"
    data = await _get_json(
        client,
        f"{svc.url.rstrip('/')}/api/{version}/{path}",
        headers={"X-Api-Key": _key(svc)},
    )
    return len(data) if isinstance(data, list) else 0


async def _check_prowlarr(client: httpx.AsyncClient, svc: Service) -> dict[str, Any]:
    why = (
        "Les indexeurs sont les sources où Sonarr et Radarr cherchent les films et les "
        "séries. Aucun installeur ne peut les choisir à ta place."
    )
    how = (
        "Dans Prowlarr : Indexers › Add Indexer, choisis une source dans la liste, "
        "clique sur Test puis Save. Ajoute-en deux ou trois. Prowlarr les transmet "
        "ensuite tout seul à Sonarr et Radarr."
    )
    try:
        n = await _arr_count(client, svc, "indexer")
    except Exception as exc:  # noqa: BLE001
        return _item(
            "indexers",
            "Ajouter des sources dans Prowlarr",
            why,
            status="error",
            detail=f"Prowlarr ne répond pas ({type(exc).__name__})",
            how=how,
            service=svc,
        )
    if n:
        return _item(
            "indexers",
            "Ajouter des sources dans Prowlarr",
            why,
            status="done",
            detail=f"{n} source{'s' if n > 1 else ''} configurée{'s' if n > 1 else ''}",
            service=svc,
            path="/indexers",
        )
    return _item(
        "indexers",
        "Ajouter des sources dans Prowlarr",
        why,
        status="todo",
        detail="Aucune source pour l'instant",
        how=how,
        service=svc,
        path="/indexers",
    )


async def _check_sabnzbd(client: httpx.AsyncClient, svc: Service) -> dict[str, Any]:
    why = (
        "SABnzbd télécharge depuis Usenet grâce à ton fournisseur (l'abonnement que tu as "
        "pris). Sans lui, les téléchargements Usenet ne peuvent pas démarrer."
    )
    how = (
        "Dans SABnzbd : Config (roue dentée) › Servers › Add Server. Renseigne l'adresse "
        "du serveur, ton identifiant et ton mot de passe, reçus à l'abonnement, puis Test "
        "Server et Add Server."
    )
    try:
        data = await _get_json(
            client,
            f"{svc.url.rstrip('/')}/api",
            params={
                "mode": "get_config",
                "section": "servers",
                "output": "json",
                "apikey": _key(svc),
            },
        )
        servers = (data.get("config") or {}).get("servers") or []
    except Exception as exc:  # noqa: BLE001
        return _item(
            "usenet",
            "Renseigner ton fournisseur Usenet",
            why,
            status="error",
            detail=f"SABnzbd ne répond pas ({type(exc).__name__})",
            how=how,
            service=svc,
        )
    if servers:
        return _item(
            "usenet",
            "Renseigner ton fournisseur Usenet",
            why,
            status="done",
            detail=f"{len(servers)} serveur{'s' if len(servers) > 1 else ''}",
            service=svc,
        )
    return _item(
        "usenet",
        "Renseigner ton fournisseur Usenet",
        why,
        status="todo",
        detail="Aucun serveur Usenet",
        how=how,
        service=svc,
        path="/config/server/",
    )


async def _check_manager(client: httpx.AsyncClient, svc: Service) -> list[dict[str, Any]]:
    """Sonarr / Radarr: a download client and a root folder are required."""
    label = LABELS[svc.type]
    what = "les séries" if svc.type == "sonarr" else "les films"
    items: list[dict[str, Any]] = []
    try:
        clients, folders = await asyncio.gather(
            _arr_count(client, svc, "downloadclient"), _arr_count(client, svc, "rootfolder")
        )
    except Exception as exc:  # noqa: BLE001
        items.append(
            _item(
                f"{svc.type}-{svc.id}",
                f"{label} prêt à télécharger",
                f"{label} doit savoir à qui confier les téléchargements et où ranger {what}.",
                status="error",
                detail=f"{label} ne répond pas ({type(exc).__name__})",
                service=svc,
            )
        )
        return items
    items.append(
        _item(
            f"{svc.type}-{svc.id}-client",
            f"{label} relié au logiciel de téléchargement",
            f"{label} confie chaque téléchargement à ton logiciel (Deluge, qBittorrent, SABnzbd).",
            status="done" if clients else "todo",
            detail=f"{clients} logiciel{'s' if clients > 1 else ''} relié{'s' if clients > 1 else ''}"
            if clients
            else "Aucun logiciel de téléchargement",
            how=(
                "Clique sur « Tout connecter » dans Paramètres › Auto-configuration : "
                "ArrMada le fait pour toi."
            )
            if not clients
            else "",
            service=svc,
            path="/settings/downloadclients",
        )
    )
    items.append(
        _item(
            f"{svc.type}-{svc.id}-folder",
            f"Dossier de rangement de {label}",
            f"C'est le dossier où {label} range {what} une fois téléchargés.",
            status="done" if folders else "todo",
            detail="Dossier défini" if folders else "Aucun dossier",
            how=(
                f"Dans {label} : Settings › Media Management › Add Root Folder, puis choisis "
                f"le dossier de {what}."
            )
            if not folders
            else "",
            service=svc,
            path="/settings/mediamanagement",
        )
    )
    return items


async def _check_jellyfin(client: httpx.AsyncClient, svc: Service) -> dict[str, Any]:
    why = "Jellyfin présente tes films et séries avec leurs affiches, sur la TV, le téléphone ou l'ordinateur."
    how = (
        "Connecte-toi à Jellyfin (identifiants ci-dessous si l'installeur l'a configuré), "
        "puis installe l'appli Jellyfin sur ta TV ou ton téléphone et entre l'adresse du serveur."
    )
    try:
        data = await _get_json(
            client,
            f"{svc.url.rstrip('/')}/Library/VirtualFolders",
            headers=jellyfin_auth(_key(svc)),
        )
        n = len(data) if isinstance(data, list) else 0
    except Exception as exc:  # noqa: BLE001
        return _item(
            "jellyfin",
            "Regarder avec Jellyfin",
            why,
            status="error",
            detail=f"Jellyfin ne répond pas ({type(exc).__name__})",
            how=how,
            service=svc,
        )
    return _item(
        "jellyfin",
        "Regarder avec Jellyfin",
        why,
        status="done" if n else "todo",
        detail=f"{n} bibliothèque{'s' if n > 1 else ''}" if n else "Aucune bibliothèque",
        how=how if not n else "Installe l'appli Jellyfin sur ta TV ou ton téléphone.",
        service=svc,
    )


async def _check_first_request(
    client: httpx.AsyncClient, managers: list[Service]
) -> dict[str, Any]:
    why = "Tout est prêt quand tu as demandé un premier film ou une première série."
    how = "Dans ArrMada : Rechercher, tape un titre, puis Ajouter. Le téléchargement démarre tout seul."
    total = 0
    for svc in managers:
        try:
            total += await _arr_count(client, svc, "series" if svc.type == "sonarr" else "movie")
        except Exception:  # noqa: BLE001 — already reported by the manager check
            continue
    item = _item(
        "first-request",
        "Demander un premier film ou une série",
        why,
        status="done" if total else "todo",
        detail=f"{total} titre{'s' if total > 1 else ''} suivi{'s' if total > 1 else ''}"
        if total
        else "Rien demandé pour l'instant",
        how="" if total else how,
    )
    item["link"] = {"url": "/search", "label": "Rechercher"}
    return item


def credentials() -> list[dict[str, str]]:
    """Passwords install.sh generated (stack.json), for the admin to copy."""
    stored = load_stack_metadata().get("credentials") or {}
    out = []
    for key in ("jellyfin", "deluge", "qbittorrent"):
        entry = stored.get(key) or {}
        if entry.get("password"):
            out.append(
                {
                    "app": LABELS[key],
                    "username": entry.get("username") or "",
                    "password": entry["password"],
                }
            )
    return out


async def build_checklist(db: AsyncSession) -> dict[str, Any]:
    services = list(
        (await db.execute(select(Service).where(Service.is_enabled.is_(True)))).scalars()
    )
    by_type: dict[str, list[Service]] = {}
    for svc in services:
        by_type.setdefault(svc.type, []).append(svc)
    managers = by_type.get("sonarr", []) + by_type.get("radarr", [])

    items: list[dict[str, Any]] = [
        _item(
            "connected",
            "Relier tes applications",
            "ArrMada retrouve Sonarr, Radarr, Prowlarr, Bazarr, ton logiciel de téléchargement "
            "et Jellyfin, puis les relie entre eux.",
            status="done" if managers else "todo",
            detail=f"{len(services)} application{'s' if len(services) > 1 else ''} reliée{'s' if len(services) > 1 else ''}"
            if managers
            else "Sonarr ou Radarr pas encore relié",
            how=""
            if managers
            else "Clique sur « Tout connecter » à l'étape « Applications » de l'assistant, "
            "ou dans Paramètres › Auto-configuration.",
        )
    ]

    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        tasks: list[Any] = []
        if by_type.get("prowlarr"):
            tasks.append(_check_prowlarr(client, by_type["prowlarr"][0]))
        for svc in by_type.get("sabnzbd", [])[:1]:
            tasks.append(_check_sabnzbd(client, svc))
        tasks.extend(_check_manager(client, svc) for svc in managers)
        for svc in by_type.get("jellyfin", [])[:1]:
            tasks.append(_check_jellyfin(client, svc))
        if managers:
            tasks.append(_check_first_request(client, managers))
        for result in await asyncio.gather(*tasks):
            items.extend(result if isinstance(result, list) else [result])

    todo = sum(1 for i in items if i["status"] == "todo")
    return {
        "items": items,
        "todo": todo,
        "done": sum(1 for i in items if i["status"] == "done"),
        "credentials": credentials(),
    }


def browser_url(url: str, host: str) -> str:
    """Docker-internal address (http://sonarr:8989) → same port on the host the browser uses."""
    parts = urlsplit(url)
    if parts.hostname and "." not in parts.hostname and parts.hostname != "localhost":
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{host}{port}{parts.path}"
    return url
