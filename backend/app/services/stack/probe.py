"""Find the URL where each app answers, from inside the ArrMada container.

A config file gives the port and URL base, but not the HOST. We try a
short list of candidates in parallel and keep those where the app answers
**with the key we read** (so we never mistake one app for another):

  1. hosts given by the user in the UI (e.g. the NAS LAN IP);
  2. hosts of the services already registered in ArrMada (same machine);
  3. the app's name as a Docker DNS name (``sonarr``, ``radarr-4k``…),
     resolved when the containers share a Docker network;
  4. the Docker host itself: default gateway of the container, then
     ``host.docker.internal`` (Docker Desktop on Windows / macOS).

Order of the resulting URLs (the first one is registered and handed to the
other apps, e.g. Prowlarr → Sonarr):

  - a Docker DNS name that answers comes FIRST: ArrMada then shares the
    apps' Docker network, and the name works from every container on it.
    The LAN IP may not: on Synology, a container on a Compose bridge network
    cannot reach its own host's LAN IP (hairpin NAT in DSM's iptables);
  - otherwise the candidate order above (apps outside Docker, other host).

Every failed attempt is classified (timeout, refused, unknown name, API key
refused, starting up, another app on that port) so the UI can say WHAT is
wrong instead of a bare « unreachable ». ``/ping`` (no key needed on the
*arr apps) separates « reachable » from « key accepted ». An app that is
still starting (HTTP 503, or connection refused on a Docker name that
resolves: the container is up, the app not yet listening) is retried a few
times with a growing delay.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import ssl
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.services.jellyfin import auth_header as jellyfin_auth
from app.services.stack.configs import FoundConfig
from app.utils.logger import get_logger

logger = get_logger(__name__)

PROBE_TIMEOUT = 3.0
# Nouveaux essais pour une appli qui démarre (secondes d'attente avant chacun)
RETRY_DELAYS = (3.0, 6.0)

# *arr apps answering ``/ping`` without an API key ({"status": "OK"})
PING_APPS = {"sonarr", "radarr", "whisparr", "lidarr", "readarr", "prowlarr"}

# Failure kinds shown to the user (hôte → libellé dans le message)
KIND_LABELS = {
    "auth": "clé API refusée",
    "starting": "en cours de démarrage",
    "wrong_app": "une autre appli répond",
    "refused": "connexion refusée",
    "timeout": "délai dépassé",
    "tls": "erreur HTTPS",
    "dns": "nom inconnu",
    "http": "réponse inattendue",
    "network": "erreur réseau",
}

# Authenticated status endpoint per app (prefix-relative, without URL base).
STATUS_PATHS = {
    "sonarr": "/api/v3/system/status",
    "radarr": "/api/v3/system/status",
    "whisparr": "/api/v3/system/status",
    "lidarr": "/api/v1/system/status",
    "readarr": "/api/v1/system/status",
    "prowlarr": "/api/v1/system/status",
    "bazarr": "/api/system/status",
}


@dataclass
class Endpoint:
    """An app reachable from ArrMada, with every URL that worked."""

    config: FoundConfig
    urls: list[str] = field(default_factory=list)  # best first
    version: str | None = None
    password_ok: bool | None = None  # downloaders: login verified?
    error: str | None = None
    #: hôte → type d'échec (timeout, refused, dns, auth, starting…)
    failures: dict[str, str] = field(default_factory=dict)

    @property
    def url(self) -> str | None:
        return self.urls[0] if self.urls else None


def default_gateway() -> str | None:
    """IPv4 default gateway of the container = the Docker host (bridge mode)."""
    try:
        for line in Path("/proc/net/route").read_text().splitlines()[1:]:
            fields = line.split()
            if len(fields) > 2 and fields[1] == "00000000":
                return socket.inet_ntoa(bytes.fromhex(fields[2])[::-1])
    except (OSError, ValueError):
        pass
    return None


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def docker_names(config: FoundConfig) -> list[str]:
    """Docker DNS names to try: folder name (radarr-4k) then the app type (radarr)."""
    names: list[str] = []
    folder = Path(config.source).parts[0].lower() if config.source else ""
    for name in (folder, config.type):
        if name and all(c.isalnum() or c in "-_." for c in name) and name not in names:
            names.append(name)
    return names


def candidate_hosts(
    config: FoundConfig, user_hosts: list[str], known_hosts: list[str]
) -> list[str]:
    """Hosts to try for one app, most portable first."""
    names = docker_names(config)
    gateway = default_gateway()
    hosts = [*user_hosts, *known_hosts, *names]
    if gateway:
        hosts.append(gateway)
    hosts.append("host.docker.internal")
    # LAN / known IPs first, then names; keep order, drop duplicates.
    return list(dict.fromkeys(h for h in hosts if h))


@dataclass
class Probe:
    """Result of one attempt on one base URL."""

    ok: bool
    kind: str = (
        "ok"  # ok | auth | starting | wrong_app | refused | timeout | tls | dns | http | network
    )
    details: dict[str, Any] = field(default_factory=dict)


def _fail(kind: str) -> Probe:
    return Probe(ok=False, kind=kind)


def _causes(exc: BaseException) -> list[BaseException]:
    """``exc`` and every exception behind it (__cause__, __context__, groups)."""
    out: list[BaseException] = []
    todo = [exc]
    while todo and len(out) < 20:
        e = todo.pop(0)
        if any(e is seen for seen in out):
            continue
        out.append(e)
        if isinstance(e, BaseExceptionGroup):
            todo.extend(e.exceptions)
        todo.extend(x for x in (e.__cause__, e.__context__) if x is not None)
    return out


def classify_error(exc: BaseException) -> str:
    """httpx / OS error → failure kind.

    Relevé sur httpx 0.28 + anyio 4 : un port fermé lève
    ``ConnectError("All connection attempts failed")``, la vraie cause
    (``ConnectionRefusedError``, errno 111) n'est que dans la chaîne des
    causes. On remonte donc la chaîne au lieu de lire le texte.
    """
    chain = _causes(exc)
    if any(isinstance(e, httpx.TimeoutException | TimeoutError) for e in chain):
        return "timeout"
    if any(isinstance(e, socket.gaierror) for e in chain):
        return "dns"
    if any(isinstance(e, ConnectionRefusedError) for e in chain):
        return "refused"
    if any(isinstance(e, ssl.SSLError) for e in chain):
        return "tls"
    # Repli sur le texte (autre version de httpx, ou erreur déjà mise en forme)
    text = " ".join(str(e).lower() for e in chain)
    if "name or service not known" in text or "name resolution" in text:
        return "dns"
    if "refused" in text:
        return "refused"
    if "ssl" in text or "certificate" in text:
        return "tls"
    return "network"


def _status_kind(code: int) -> str:
    if code in (401, 403):
        return "auth"
    if code in (502, 503, 504):
        return "starting"
    return "http"


async def _check(
    client: httpx.AsyncClient, config: FoundConfig, base: str, password: str | None
) -> Probe:
    """Is ``base`` really this app (authenticated)? Classified result."""
    t = config.type
    try:
        if t in STATUS_PATHS:
            if t in PING_APPS:
                # /ping répond sans clé : il sépare « l'appli ne répond pas » (erreur
                # réseau, levée ici) de « l'appli répond mais refuse la clé » (401
                # plus bas). Seul un 5xx (proxy devant une appli qui démarre) s'arrête
                # là ; tout autre code laisse trancher l'appel authentifié.
                ping = await client.get(f"{base}/ping")
                if ping.status_code in (502, 503, 504):
                    return _fail("starting")
            resp = await client.get(
                f"{base}{STATUS_PATHS[t]}", headers={"X-Api-Key": config.api_key or ""}
            )
            if resp.status_code != 200:
                return _fail(_status_kind(resp.status_code))
            data = resp.json()
            # Bazarr wraps its payload in {"data": {...}}
            data = data.get("data", data) if isinstance(data, dict) else {}
            app_name = str(data.get("appName") or data.get("instanceName") or t).lower()
            if t != "bazarr" and t not in app_name:
                return _fail("wrong_app")  # another *arr on that port
            return Probe(
                True, details={"version": data.get("version") or data.get("bazarr_version")}
            )
        if t == "sabnzbd":
            resp = await client.get(
                f"{base}/api",
                params={"mode": "version", "apikey": config.api_key, "output": "json"},
            )
            if resp.status_code != 200:
                return _fail(_status_kind(resp.status_code))
            # mode=version answers without a key: check the key with a keyed call.
            auth = await client.get(
                f"{base}/api",
                params={"mode": "queue", "limit": 1, "apikey": config.api_key, "output": "json"},
            )
            if auth.status_code != 200 or "queue" not in auth.text:
                return _fail("auth" if auth.status_code in (200, 401, 403) else "http")
            return Probe(True, details={"version": resp.json().get("version")})
        if t == "deluge":
            resp = await client.post(
                f"{base}/json", json={"method": "auth.check_session", "params": [], "id": 1}
            )
            if resp.status_code != 200 or "result" not in resp.text:
                return _fail(
                    _status_kind(resp.status_code) if resp.status_code != 200 else "wrong_app"
                )
            details: dict[str, Any] = {"version": None, "password_ok": None}
            if password:
                login = await client.post(
                    f"{base}/json", json={"method": "auth.login", "params": [password], "id": 2}
                )
                details["password_ok"] = (
                    login.status_code == 200 and login.json().get("result") is True
                )
            return Probe(True, details=details)
        if t == "qbittorrent":
            resp = await client.get(f"{base}/api/v2/app/version")
            # Unauthenticated: 403 "Forbidden". Whitelisted subnet: 200 + version.
            if resp.status_code not in (200, 403) or "<html" in resp.text.lower():
                return _fail(
                    _status_kind(resp.status_code)
                    if resp.status_code not in (200, 403)
                    else "wrong_app"
                )
            details = {
                "version": resp.text.strip() if resp.status_code == 200 else None,
                "password_ok": None,
            }
            if resp.status_code == 200:
                details["password_ok"] = True  # no auth needed from ArrMada's subnet
            elif password:
                login = await client.post(
                    f"{base}/api/v2/auth/login",
                    data={"username": config.username or "admin", "password": password},
                    headers={"Referer": base},
                )
                # qBittorrent < 5: 200 "Ok." + cookie SID.
                # qBittorrent ≥ 5: 204 (vide) + cookie QBT_SID_<port>.
                details["password_ok"] = login.status_code in (200, 204) and (
                    login.text.strip() == "Ok." or any("SID" in name for name in login.cookies)
                )
            return Probe(True, details=details)
        if t == "jellyfin":
            if not config.api_key:
                # No key yet: still locate it (public endpoint), so the UI says
                # "create an API key" instead of a misleading "unreachable".
                resp = await client.get(f"{base}/System/Info/Public")
                if resp.status_code != 200 or "Jellyfin" not in resp.text:
                    return _fail(
                        _status_kind(resp.status_code) if resp.status_code != 200 else "wrong_app"
                    )
                return Probe(True, details={"version": resp.json().get("Version")})
            resp = await client.get(f"{base}/System/Info", headers=jellyfin_auth(config.api_key))
            if resp.status_code != 200:
                return _fail(_status_kind(resp.status_code))
            return Probe(True, details={"version": resp.json().get("Version")})
    except (httpx.HTTPError, OSError) as exc:
        return _fail(classify_error(exc))
    except ValueError:
        return _fail("http")  # pas du JSON : autre chose répond sur ce port
    return _fail("http")


def _retryable(kind: str, host: str, names: list[str]) -> bool:
    """Worth another try: the app is starting (503), or its container name
    resolves but nothing listens yet (refused)."""
    return kind == "starting" or (kind == "refused" and host in names)


def explain(config: FoundConfig, failures: dict[str, str], *, detail: bool = True) -> str:
    """French message for an app found nowhere, from the most useful failure.

    ``detail`` ajoute la liste des adresses essayées (inutile pour une seule).
    """
    name, port = config.name, config.port
    kinds = set(failures.values())
    tried = ", ".join(f"{h} ({KIND_LABELS.get(k, k)})" for h, k in list(failures.items())[:6])
    tried = tried if detail else ""
    if "auth" in kinds:
        head = (
            f"{name} répond mais refuse la clé API : celle de son fichier de config a peut-être "
            f"changé. Redémarre {name} puis relance l'analyse, ou saisis la clé à la main."
        )
    elif "starting" in kinds:
        head = f"{name} est en cours de démarrage : réessaie dans une minute."
    elif "wrong_app" in kinds:
        head = f"Une autre application que {name} répond sur le port {port} : vérifie le port."
    elif "refused" in kinds:
        head = (
            f"Connexion refusée sur le port {port} : {name} ne tourne pas, ou écoute sur un "
            "autre port."
        )
    elif "timeout" in kinds:
        head = (
            f"Délai dépassé sur le port {port} : l'hôte ne répond pas. Sur un NAS Synology, un "
            "conteneur ne peut souvent pas joindre l'IP du NAS lui-même : place ArrMada sur le "
            f"même réseau Docker que {name}, il sera alors joint par son nom."
        )
    elif kinds == {"dns"}:
        head = f"{name} introuvable : indique l'IP de la machine qui l'héberge."
    else:
        head = f"{name} injoignable sur le port {port}. Indique l'IP de la machine qui l'héberge."
    return f"{head} (essayé : {tried})" if tried else head


async def locate(
    config: FoundConfig,
    *,
    user_hosts: list[str] | None = None,
    known_hosts: list[str] | None = None,
    password: str | None = None,
    retry_delays: tuple[float, ...] = RETRY_DELAYS,
) -> Endpoint:
    """Probe every candidate host for one app (in parallel)."""
    endpoint = Endpoint(config=config)
    scheme = "https" if config.ssl else "http"
    hosts = candidate_hosts(config, user_hosts or [], known_hosts or [])
    names = docker_names(config)
    password = password or config.password

    def base_of(host: str) -> str:
        return f"{scheme}://{host}:{config.port}{config.url_base}"

    results: dict[str, Probe] = {}
    pending = list(hosts)
    async with httpx.AsyncClient(
        timeout=PROBE_TIMEOUT, verify=False, follow_redirects=False
    ) as client:
        for attempt in range(len(retry_delays) + 1):
            probes = await asyncio.gather(
                *(_check(client, config, base_of(h), password) for h in pending)
            )
            results.update(zip(pending, probes, strict=True))
            if any(p.ok for p in results.values()) or attempt == len(retry_delays):
                break
            pending = [h for h, p in results.items() if _retryable(p.kind, h, names)]
            if not pending:
                break
            logger.info(
                "%s pas encore prêt (%s), nouvel essai dans %.0f s",
                config.name,
                ", ".join(pending),
                retry_delays[attempt],
            )
            await asyncio.sleep(retry_delays[attempt])

    # Nom Docker qui répond en premier (voir docstring), puis ordre des candidats
    working = [h for h in hosts if results[h].ok]
    working.sort(key=lambda h: 0 if h in names else 1)
    for host in working:
        details = results[host].details
        endpoint.urls.append(base_of(host))
        endpoint.version = endpoint.version or details.get("version")
        if details.get("password_ok") is not None:
            endpoint.password_ok = bool(endpoint.password_ok) or details["password_ok"]

    endpoint.failures = {h: p.kind for h, p in results.items() if not p.ok}
    if not endpoint.urls:
        endpoint.error = explain(config, endpoint.failures)
    logger.info("Located %s: %s", config.name, endpoint.urls or endpoint.error)
    return endpoint


#: Types que ``_check`` sait sonder (les autres n'ont pas de diagnostic)
PROBED_TYPES = {*STATUS_PATHS, "sabnzbd", "deluge", "qbittorrent", "jellyfin"}


@dataclass
class Diagnosis:
    """Why a registered URL fails, and a Docker name that works instead."""

    ok: bool
    kind: str
    message: str | None = None
    suggested_url: str | None = None


async def diagnose_url(
    service_type: str,
    url: str,
    api_key: str,
    name: str,
    *,
    retry_delays: tuple[float, ...] = (),
) -> Diagnosis:
    """Health check help (« Tester », Paramètres › Services).

    Probes the stored URL with the same classified checks as the detection.
    If it fails (typically the NAS LAN IP, hairpin on Synology) but the app
    answers on a Docker name (its type, or its name as a slug) with the same
    port, URL base and key, that URL is proposed instead.
    """
    parsed = httpx.URL(url)
    host = parsed.host or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    config = FoundConfig(
        type=service_type,
        name=name,
        port=port,
        source="",
        api_key=api_key,
        url_base=parsed.path.rstrip("/"),
        ssl=parsed.scheme == "https",
    )
    slug = "".join(c for c in name.lower().replace(" ", "-") if c.isalnum() or c in "-_.")
    names = [h for h in dict.fromkeys([service_type, slug]) if h and h != host]
    # Deluge : son mot de passe est stocké à la place de la clé API
    password = api_key if service_type == "deluge" else None
    endpoint = await locate(
        config,
        user_hosts=[host],
        known_hosts=names,
        password=password,
        retry_delays=retry_delays,
    )
    hosts = {httpx.URL(u).host: u for u in endpoint.urls}
    if host in hosts:
        return Diagnosis(ok=True, kind="ok")
    kind = endpoint.failures.get(host, "network")
    # Seulement un nom Docker de l'appli : stable, et joignable depuis les autres
    # conteneurs du même réseau (pas la passerelle, ni host.docker.internal).
    suggested = next((hosts[n] for n in names if n in hosts), None)
    if suggested and kind == "timeout":
        # Le nom Docker répond : ArrMada est déjà sur le bon réseau, le conseil
        # « rejoins le réseau Docker » serait faux. C'est l'adresse qui pèche.
        message = (
            f"Délai dépassé sur {host}:{port} : depuis le conteneur ArrMada, cette adresse ne "
            "répond pas (fréquent avec l'IP du NAS sur Synology)."
        )
    else:
        message = explain(config, {host: kind}, detail=False)
    return Diagnosis(ok=False, kind=kind, message=message, suggested_url=suggested)


def host_of(url: str) -> str | None:
    """Host part of a stored service URL (to reuse it as a candidate)."""
    try:
        return httpx.URL(url).host or None
    except Exception:  # noqa: BLE001
        return None


def lan_first(hosts: list[str]) -> list[str]:
    """Private IPs first (most likely the NAS LAN address), then the rest."""

    def rank(h: str) -> int:
        if (
            _is_ip(h)
            and ipaddress.ip_address(h).is_private
            and not ipaddress.ip_address(h).is_loopback
        ):
            return 0
        return 1

    return sorted(dict.fromkeys(hosts), key=rank)
