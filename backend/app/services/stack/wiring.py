"""Wire the stack together: plan first, then apply (like terraform).

``build_plan`` inspects every app and lists what is missing:

  register        add the app to ArrMada (its key was read from appdata)
  prowlarr_app    Prowlarr → Settings → Apps → Sonarr/Radarr/Lidarr/Readarr
  download_client Sonarr/Radarr/… → Settings → Download clients → SABnzbd/Deluge/qBittorrent
  bazarr_link     Bazarr → Settings → Sonarr / Radarr
  root_folder     Sonarr/Radarr → Media management → Root folders (TRaSH layout,
                  only when install.sh created the stack: see ``stack.json``)

Each action is idempotent: if the target already has an equivalent entry
(same implementation, same port) it is reported as ``done`` and never
duplicated. ``apply_plan`` recomputes the plan server-side (the client only
sends action ids), asks the TARGET app to test the new entry with its own
``/test`` endpoint (so the URL is validated from ITS container, not ours),
and only then saves it. If several URLs reached an app, they are tried in
order until one passes the test.
"""

from __future__ import annotations

import asyncio
import copy
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.service import Service
from app.services import encryption
from app.services.stack.configs import FoundConfig, scan_appdata
from app.services.stack.probe import host_of, lan_first, locate
from app.utils.logger import get_logger

logger = get_logger(__name__)

HTTP_TIMEOUT = 15.0

# Service types ArrMada itself can register (see models.service.Service).
REGISTRABLE = ("sonarr", "radarr", "lidarr", "readarr", "prowlarr", "bazarr", "jellyfin", "sabnzbd")
# Apps that receive Prowlarr indexers and download clients.
MANAGERS = ("sonarr", "radarr", "lidarr", "readarr")
DOWNLOADERS = ("sabnzbd", "deluge", "qbittorrent")

API_PREFIX = {
    "sonarr": "/api/v3",
    "radarr": "/api/v3",
    "lidarr": "/api/v1",
    "readarr": "/api/v1",
    "prowlarr": "/api/v1",
}
IMPLEMENTATION = {
    "sonarr": "Sonarr",
    "radarr": "Radarr",
    "lidarr": "Lidarr",
    "readarr": "Readarr",
    "sabnzbd": "Sabnzbd",
    "deluge": "Deluge",
    "qbittorrent": "QBittorrent",
}
# Download category per manager (SABnzbd defaults: tv, movies, audio).
CATEGORY = {"sonarr": "tv", "radarr": "movies", "lidarr": "audio", "readarr": "books"}
CATEGORY_FIELDS = ("tvCategory", "movieCategory", "musicCategory", "bookCategory")

LABEL = {
    "sonarr": "Sonarr",
    "radarr": "Radarr",
    "lidarr": "Lidarr",
    "readarr": "Readarr",
    "prowlarr": "Prowlarr",
    "bazarr": "Bazarr",
    "jellyfin": "Jellyfin",
    "sabnzbd": "SABnzbd",
    "deluge": "Deluge",
    "qbittorrent": "qBittorrent",
}


# ── Model ─────────────────────────────────────────────────────
@dataclass
class App:
    """One app of the stack, from ArrMada's database and/or its config file."""

    type: str
    name: str
    urls: list[str] = field(default_factory=list)
    api_key: str | None = None
    username: str | None = None
    password: str | None = None
    version: str | None = None
    service_id: int | None = None  # already registered in ArrMada
    source: str = "arrmada"  # arrmada | appdata | manual
    config_path: str | None = None
    error: str | None = None
    notes: list[str] = field(default_factory=list)
    needs_password: bool = False

    @property
    def url(self) -> str | None:
        return self.urls[0] if self.urls else None

    @property
    def usable(self) -> bool:
        """Reachable AND we hold the credentials it needs."""
        return bool(self.urls) and not self.needs_password

    def public(self) -> dict[str, Any]:
        """Serializable view WITHOUT secrets (sent to the browser)."""
        data = asdict(self)
        data.pop("api_key")
        data.pop("password")
        data["url"] = self.url
        data["has_api_key"] = bool(self.api_key)
        data["registered"] = self.service_id is not None
        return data


@dataclass
class Action:
    id: str
    kind: str
    target: str  # app that will be modified (name)
    subject: str  # app it points to (name)
    title: str
    status: str = "todo"  # todo | done | blocked
    reason: str | None = None


@dataclass
class Plan:
    apps: list[App]
    actions: list[Action]
    appdata_dir: str
    appdata_mounted: bool

    def public(self) -> dict[str, Any]:
        return {
            "appdata_dir": self.appdata_dir,
            "appdata_mounted": self.appdata_mounted,
            "apps": [a.public() for a in self.apps],
            "actions": [asdict(a) for a in self.actions],
        }


# ── Inventory ─────────────────────────────────────────────────
def _from_config(
    cfg: FoundConfig, endpoint_urls: list[str], version: str | None, error: str | None
) -> App:
    return App(
        type=cfg.type,
        name=cfg.name,
        urls=endpoint_urls,
        api_key=cfg.api_key,
        username=cfg.username,
        password=cfg.password,
        version=version,
        source="appdata",
        config_path=cfg.source,
        error=error,
        notes=list(cfg.notes),
        needs_password=cfg.needs_password,
    )


def load_stack_metadata() -> dict[str, Any]:
    """``DATA_DIR/stack.json``, written by install.sh (0600, owned by PUID).

    Holds the torrent passwords install.sh generated (Deluge / qBittorrent
    only keep a hash: we could not read them back) and the TRaSH root
    folders. Absent for stacks not created by the installer.
    """
    path = Path(settings.DATA_DIR) / "stack.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


async def build_inventory(
    db: AsyncSession,
    *,
    user_hosts: list[str] | None = None,
    credentials: dict[str, dict[str, str]] | None = None,
) -> tuple[list[App], bool]:
    """Merge ArrMada's registered services with the configs found in appdata."""
    # Passwords typed in the UI win over the ones install.sh generated.
    stored = load_stack_metadata().get("credentials") or {}
    credentials = {
        k: {**(stored.get(k) or {}), **(credentials or {}).get(k, {})}
        for k in {*stored, *(credentials or {})}
        if isinstance(stored.get(k, {}), dict)
    }
    user_hosts = [h.strip() for h in (user_hosts or []) if h and h.strip()]

    rows = (await db.execute(select(Service).where(Service.type.in_(REGISTRABLE)))).scalars().all()
    apps: list[App] = []
    for svc in rows:
        try:
            key = encryption.decrypt_api_key(svc.api_key)
        except Exception:  # noqa: BLE001 — undecryptable key: keep the app, flag it
            key = None
        apps.append(
            App(
                type=svc.type,
                name=svc.name,
                urls=[svc.url.rstrip("/")],
                api_key=key,
                version=svc.version,
                service_id=svc.id,
                error=None if key else "Clé API illisible (clé de chiffrement changée ?)",
            )
        )
    known_hosts = lan_first([h for h in (host_of(a.url or "") for a in apps) if h])

    configs = scan_appdata(settings.APPDATA_DIR)
    todo: list[FoundConfig] = []
    for cfg in configs:
        # Already registered (same type + same key)? Enrich, don't duplicate.
        twin = next(
            (a for a in apps if a.type == cfg.type and cfg.api_key and a.api_key == cfg.api_key),
            None,
        )
        if twin:
            twin.config_path = cfg.source
            continue
        # Same key as a config found just before (copy of the same app): keep one.
        if any(t.type == cfg.type and cfg.api_key and t.api_key == cfg.api_key for t in todo):
            continue
        creds = credentials.get(cfg.type, {})
        if cfg.type in ("deluge", "qbittorrent") and creds.get("password"):
            if cfg.password_check and not cfg.check_password(creds["password"]):
                cfg.notes.append(
                    "Le mot de passe saisi ne correspond pas à celui de la configuration."
                )
            else:
                cfg.password = creds["password"]
                cfg.username = creds.get("username") or cfg.username
        todo.append(cfg)

    # Toutes les applis sondées EN MÊME TEMPS : une appli qui démarre est
    # réessayée quelques secondes (voir probe.locate), sans retarder les autres.
    endpoints = await asyncio.gather(
        *(
            locate(cfg, user_hosts=user_hosts, known_hosts=known_hosts, password=cfg.password)
            for cfg in todo
        )
    )
    for cfg, endpoint in zip(todo, endpoints, strict=True):
        app = _from_config(cfg, endpoint.urls, endpoint.version, endpoint.error)
        if endpoint.password_ok is True and cfg.type == "qbittorrent" and not app.password:
            app.needs_password = False  # subnet whitelisted: no login required
        if endpoint.password_ok is False:
            app.needs_password = True
            app.notes.append("Connexion refusée avec ce mot de passe.")
        apps.append(app)

    # Downloaders typed in by hand (no appdata mount).
    for dl in ("deluge", "qbittorrent"):
        creds = credentials.get(dl, {})
        if creds.get("url") and not any(a.type == dl for a in apps):
            apps.append(
                App(
                    type=dl,
                    name=LABEL[dl],
                    urls=[creds["url"].rstrip("/")],
                    username=creds.get("username") or ("admin" if dl == "qbittorrent" else None),
                    password=creds.get("password"),
                    source="manual",
                    needs_password=not creds.get("password"),
                )
            )

    apps.sort(key=lambda a: (list(LABEL).index(a.type) if a.type in LABEL else 99, a.name))
    # Names identify apps in action ids: make them unique ("Sonarr", "Sonarr #2").
    seen: dict[str, int] = {}
    for app in apps:
        seen[app.name] = seen.get(app.name, 0) + 1
        if seen[app.name] > 1:
            app.name = f"{app.name} #{seen[app.name]}"
    return apps, bool(configs) or _appdata_mounted()


def _appdata_mounted() -> bool:
    root = Path(settings.APPDATA_DIR)
    return root.is_dir() and any(root.iterdir())


# ── HTTP helpers ──────────────────────────────────────────────
def _arr_client(app: App, base: str | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=f"{(base or app.url or '').rstrip('/')}{API_PREFIX[app.type]}",
        headers={"X-Api-Key": app.api_key or ""},
        timeout=HTTP_TIMEOUT,
        verify=False,
    )


def _split(url: str) -> tuple[str, int, bool, str]:
    """host, port, ssl, url_base of an app URL."""
    parts = urlsplit(url)
    ssl = parts.scheme == "https"
    return parts.hostname or "", parts.port or (443 if ssl else 80), ssl, parts.path.rstrip("/")


def _field_value(item: dict, name: str) -> Any:
    for f in item.get("fields", []):
        if f.get("name") == name:
            return f.get("value")
    return None


def _set_fields(template: dict, values: dict[str, Any]) -> dict:
    for f in template.get("fields", []):
        if f.get("name") in values:
            f["value"] = values[f["name"]]
    return template


def _same_port(url_a: str | None, url_b: str | None) -> bool:
    if not url_a or not url_b:
        return False
    try:
        return _split(url_a)[1] == _split(url_b)[1]
    except ValueError:
        return False


def _error_text(resp: httpx.Response) -> str:
    """Readable validation message from an *arr 400 response."""
    try:
        body = resp.json()
    except ValueError:
        return f"HTTP {resp.status_code}"
    if isinstance(body, list):
        msgs = [
            b.get("errorMessage") for b in body if isinstance(b, dict) and b.get("errorMessage")
        ]
        if msgs:
            return " ; ".join(msgs)
    if isinstance(body, dict):
        return str(body.get("message") or body.get("detail") or body)[:300]
    return str(body)[:300]


# ── Plan ──────────────────────────────────────────────────────
async def _existing(app: App, path: str) -> list[dict] | None:
    try:
        async with _arr_client(app) as client:
            resp = await client.get(path)
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Cannot read %s%s: %s", app.name, path, exc)
        return None


async def _bazarr_settings(app: App) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=False) as client:
            resp = await client.get(
                f"{app.url}/api/system/settings", headers={"X-API-KEY": app.api_key or ""}
            )
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Cannot read Bazarr settings: %s", exc)
        return None


def _blocked_reason(app: App) -> str | None:
    if not app.urls:
        return f"{app.name} injoignable"
    if app.needs_password:
        return f"mot de passe {app.name} requis"
    if app.type not in ("deluge", "qbittorrent") and not app.api_key:
        return f"clé API {app.name} inconnue"
    return None


async def build_plan(
    db: AsyncSession,
    *,
    user_hosts: list[str] | None = None,
    credentials: dict[str, dict[str, str]] | None = None,
) -> Plan:
    apps, mounted = await build_inventory(db, user_hosts=user_hosts, credentials=credentials)
    actions: list[Action] = []

    # 1. Register in ArrMada
    for app in apps:
        if app.service_id is None and app.type in REGISTRABLE:
            actions.append(
                Action(
                    id=f"register:{app.type}:{app.config_path or app.url}",
                    kind="register",
                    target="ArrMada",
                    subject=app.name,
                    title=f"Ajouter {app.name} à ArrMada",
                    status="blocked" if _blocked_reason(app) else "todo",
                    reason=_blocked_reason(app),
                )
            )

    managers = [a for a in apps if a.type in MANAGERS]

    # 2. Prowlarr → apps
    for prowlarr in (a for a in apps if a.type == "prowlarr"):
        existing = await _existing(prowlarr, "/applications") if prowlarr.usable else None
        for mgr in managers:
            action = Action(
                id=f"prowlarr_app:{prowlarr.name}:{mgr.name}",
                kind="prowlarr_app",
                target=prowlarr.name,
                subject=mgr.name,
                title=f"{prowlarr.name} : synchroniser les indexeurs vers {mgr.name}",
            )
            blocked = _blocked_reason(prowlarr) or _blocked_reason(mgr)
            if blocked:
                action.status, action.reason = "blocked", blocked
            elif existing is None:
                action.status, action.reason = (
                    "blocked",
                    f"lecture des applications de {prowlarr.name} impossible",
                )
            elif any(
                e.get("implementation") == IMPLEMENTATION[mgr.type]
                and any(_same_port(_field_value(e, "baseUrl"), u) for u in mgr.urls)
                for e in existing
            ):
                action.status = "done"
            actions.append(action)

    # 3. Download clients in each manager
    downloaders = [a for a in apps if a.type in DOWNLOADERS]
    for mgr in managers:
        existing = await _existing(mgr, "/downloadclient") if mgr.usable else None
        for dl in downloaders:
            action = Action(
                id=f"download_client:{mgr.name}:{dl.name}",
                kind="download_client",
                target=mgr.name,
                subject=dl.name,
                title=f"{mgr.name} : ajouter le client de téléchargement {dl.name}",
            )
            blocked = _blocked_reason(mgr) or _blocked_reason(dl)
            if blocked:
                action.status, action.reason = "blocked", blocked
            elif existing is None:
                action.status, action.reason = (
                    "blocked",
                    f"lecture des clients de {mgr.name} impossible",
                )
            elif any(
                e.get("implementation") == IMPLEMENTATION[dl.type]
                and any(_same_port(f"http://x:{_field_value(e, 'port')}", u) for u in dl.urls)
                for e in existing
            ):
                action.status = "done"
            actions.append(action)

    # 4. Bazarr → first Sonarr and first Radarr (Bazarr handles one of each)
    for bazarr in (a for a in apps if a.type == "bazarr"):
        current = await _bazarr_settings(bazarr) if bazarr.usable else None
        for kind in ("sonarr", "radarr"):
            mgr = next((m for m in managers if m.type == kind), None)
            if not mgr:
                continue
            action = Action(
                id=f"bazarr_link:{bazarr.name}:{mgr.name}",
                kind="bazarr_link",
                target=bazarr.name,
                subject=mgr.name,
                title=f"{bazarr.name} : connecter {mgr.name} (sous-titres)",
            )
            blocked = _blocked_reason(bazarr) or _blocked_reason(mgr)
            if blocked:
                action.status, action.reason = "blocked", blocked
            elif current is None:
                action.status, action.reason = (
                    "blocked",
                    f"lecture des réglages de {bazarr.name} impossible",
                )
            elif (current.get("general") or {}).get(f"use_{kind}") and (
                current.get(kind) or {}
            ).get("apikey"):
                action.status = "done"
            actions.append(action)

    # 5. Root folders (TRaSH layout created by install.sh)
    root_folders = load_stack_metadata().get("root_folders") or {}
    for mgr in managers:
        path = root_folders.get(mgr.type)
        if not path or not mgr.usable:
            continue
        existing = await _existing(mgr, "/rootfolder")
        if existing is None:
            continue
        paths = {str(e.get("path", "")).rstrip("/") for e in existing}
        if paths and path.rstrip("/") not in paths:
            continue  # the user already chose other root folders: leave them
        actions.append(
            Action(
                id=f"root_folder:{mgr.name}:{path}",
                kind="root_folder",
                target=mgr.name,
                subject=path,
                title=f"{mgr.name} : dossier médias {path}",
                status="done" if paths else "todo",
            )
        )

    return Plan(
        apps=apps, actions=actions, appdata_dir=settings.APPDATA_DIR, appdata_mounted=mounted
    )


# ── Apply ─────────────────────────────────────────────────────
@dataclass
class ActionResult:
    id: str
    ok: bool
    message: str


def _app(plan: Plan, name: str) -> App:
    return next(a for a in plan.apps if a.name == name)


async def _register(db: AsyncSession, app: App) -> str:
    db.add(
        Service(
            name=app.name,
            type=app.type,
            url=app.url,
            api_key=encryption.encrypt_api_key(app.api_key or ""),
            is_enabled=True,
        )
    )
    await db.flush()
    return f"{app.name} ajouté ({app.url})"


def _only_warnings(resp: httpx.Response) -> bool:
    """*arr validation answered 400 with warnings only (e.g. "A category is recommended")."""
    try:
        body = resp.json()
    except ValueError:
        return False
    return (
        isinstance(body, list)
        and bool(body)
        and all(isinstance(b, dict) and b.get("isWarning") for b in body)
    )


async def _test_then_save(client: httpx.AsyncClient, path: str, payload: dict) -> str | None:
    """POST {path}/test then {path}; returns an error message or None.

    - real error → one retry 2 s later: a freshly started SABnzbd/Deluge
      sometimes fails the first test (seen in practice);
    - warnings only → saved anyway (``forceSave``, like the UI's "Save anyway").
    """
    test = await client.post(f"{path}/test", json=payload)
    if test.status_code >= 400 and not _only_warnings(test):
        await asyncio.sleep(2)
        test = await client.post(f"{path}/test", json=payload)
    if test.status_code >= 400 and not _only_warnings(test):
        return _error_text(test)
    params = {"forceSave": "true"} if test.status_code >= 400 else None
    saved = await client.post(path, json=payload, params=params)
    if saved.status_code >= 400:
        return _error_text(saved)
    return None


async def _schema(client: httpx.AsyncClient, path: str, implementation: str) -> dict:
    resp = await client.get(f"{path}/schema")
    resp.raise_for_status()
    template = next((s for s in resp.json() if s.get("implementation") == implementation), None)
    if template is None:
        raise ValueError(f"implémentation {implementation} absente du schéma")
    return template


async def _prowlarr_app(prowlarr: App, mgr: App) -> str:
    errors: list[str] = []
    async with _arr_client(prowlarr) as client:
        template = await _schema(client, "/applications", IMPLEMENTATION[mgr.type])
        for mgr_url in mgr.urls:
            payload = _set_fields(
                copy.deepcopy(template),
                {"prowlarrUrl": prowlarr.url, "baseUrl": mgr_url, "apiKey": mgr.api_key},
            )
            payload.update({"name": mgr.name, "syncLevel": "fullSync", "enable": True})
            error = await _test_then_save(client, "/applications", payload)
            if error is None:
                return f"{mgr.name} ajouté dans {prowlarr.name} ({mgr_url})"
            errors.append(f"{mgr_url} : {error}")
    raise RuntimeError(" | ".join(errors))


async def _prepare_downloader(dl: App, category: str) -> None:
    """Make the category usable on the downloader side (best effort).

    SABnzbd: create the category if missing (``books`` is not a default).
    Deluge:  categories are labels → enable the Label plugin (off by default).
    Any failure is ignored: the caller then falls back to "no category".
    """
    try:
        async with httpx.AsyncClient(
            base_url=dl.url or "", timeout=HTTP_TIMEOUT, verify=False
        ) as client:
            if dl.type == "sabnzbd":
                base = {"apikey": dl.api_key, "output": "json"}
                cats = (
                    (await client.get("/api", params={**base, "mode": "get_cats"}))
                    .json()
                    .get("categories", [])
                )
                if category not in cats:
                    await client.get(
                        "/api",
                        params={
                            **base,
                            "mode": "set_config",
                            "section": "categories",
                            "keyword": category,
                            "name": category,
                        },
                    )
            elif dl.type == "deluge":

                async def rpc(method: str, params: list | None = None) -> Any:
                    resp = await client.post(
                        "/json", json={"method": method, "params": params or [], "id": 1}
                    )
                    return resp.json().get("result")

                if not await rpc("auth.login", [dl.password or ""]):
                    return
                if not await rpc("web.connected"):
                    hosts = await rpc("web.get_hosts") or []
                    if hosts:
                        await rpc("web.connect", [hosts[0][0]])
                if "Label" not in (await rpc("core.get_enabled_plugins") or []):
                    await rpc("core.enable_plugin", ["Label"])
                    await asyncio.sleep(1)
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        logger.info("Could not prepare category on %s: %s", dl.name, exc)


async def _download_client(mgr: App, dl: App) -> str:
    errors: list[str] = []
    await _prepare_downloader(dl, CATEGORY[mgr.type])
    async with _arr_client(mgr) as client:
        template = await _schema(client, "/downloadclient", IMPLEMENTATION[dl.type])
        category_field = next(
            (f["name"] for f in template.get("fields", []) if f.get("name") in CATEGORY_FIELDS),
            None,
        )
        for dl_url in dl.urls:
            host, port, ssl, url_base = _split(dl_url)
            values: dict[str, Any] = {
                "host": host,
                "port": port,
                "useSsl": ssl,
                "urlBase": url_base,
            }
            if dl.type == "sabnzbd":
                values["apiKey"] = dl.api_key
            elif dl.type == "deluge":
                values["password"] = dl.password
            else:
                values.update({"username": dl.username or "", "password": dl.password or ""})
            # With a category first (TRaSH layout), then without: Deluge needs
            # its Label plugin for categories, which is often disabled.
            attempts = [True, False] if category_field else [False]
            for with_category in attempts:
                fields = dict(values)
                if with_category:
                    fields[category_field] = CATEGORY[mgr.type]
                elif category_field:
                    fields[category_field] = ""
                payload = _set_fields(copy.deepcopy(template), fields)
                payload.update({"name": dl.name, "enable": True, "priority": 1})
                error = await _test_then_save(client, "/downloadclient", payload)
                if error is None:
                    suffix = (
                        f", catégorie « {CATEGORY[mgr.type]} »"
                        if with_category
                        else ", sans catégorie"
                    )
                    return f"{dl.name} ajouté dans {mgr.name} ({host}:{port}{suffix})"
                errors.append(f"{host}:{port}{' + catégorie' if with_category else ''} : {error}")
    raise RuntimeError(" | ".join(errors))


async def _root_folder(mgr: App, path: str) -> str:
    async with _arr_client(mgr) as client:
        resp = await client.post("/rootfolder", json={"path": path})
        if resp.status_code >= 400:
            raise RuntimeError(_error_text(resp))
    return f"{path} ajouté comme dossier racine de {mgr.name}"


async def _bazarr_link(bazarr: App, mgr: App) -> str:
    host, port, ssl, url_base = _split(mgr.url or "")
    kind = mgr.type
    form = {
        f"settings-general-use_{kind}": "true",
        f"settings-{kind}-ip": host,
        f"settings-{kind}-port": str(port),
        f"settings-{kind}-base_url": url_base or "/",
        f"settings-{kind}-ssl": "true" if ssl else "false",
        f"settings-{kind}-apikey": mgr.api_key or "",
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, verify=False) as client:
        resp = await client.post(
            f"{bazarr.url}/api/system/settings",
            data=form,
            headers={"X-API-KEY": bazarr.api_key or ""},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} : {resp.text[:200]}")
    return f"{mgr.name} connecté à {bazarr.name} ({host}:{port})"


async def apply_plan(
    db: AsyncSession,
    action_ids: list[str],
    *,
    user_hosts: list[str] | None = None,
    credentials: dict[str, dict[str, str]] | None = None,
) -> tuple[list[ActionResult], Plan]:
    """Run the selected ``todo`` actions, one by one (never in parallel)."""
    plan = await build_plan(db, user_hosts=user_hosts, credentials=credentials)
    wanted = set(action_ids)
    results: list[ActionResult] = []
    for action in plan.actions:
        if action.id not in wanted:
            continue
        if action.status != "todo":
            results.append(
                ActionResult(action.id, action.status == "done", action.reason or "déjà en place")
            )
            continue
        try:
            if action.kind == "register":
                message = await _register(db, _app(plan, action.subject))
            elif action.kind == "prowlarr_app":
                message = await _prowlarr_app(_app(plan, action.target), _app(plan, action.subject))
            elif action.kind == "download_client":
                message = await _download_client(
                    _app(plan, action.target), _app(plan, action.subject)
                )
            elif action.kind == "bazarr_link":
                message = await _bazarr_link(_app(plan, action.target), _app(plan, action.subject))
            elif action.kind == "root_folder":
                message = await _root_folder(_app(plan, action.target), action.subject)
            else:  # pragma: no cover - plan only emits the kinds above
                raise RuntimeError(f"type d'action inconnu : {action.kind}")
            results.append(ActionResult(action.id, True, message))
            logger.info("Stack wiring OK — %s: %s", action.id, message)
        except Exception as exc:  # noqa: BLE001 — report per action, keep going
            logger.warning("Stack wiring FAILED — %s: %s", action.id, exc)
            results.append(ActionResult(action.id, False, str(exc) or exc.__class__.__name__))
    return results, plan
