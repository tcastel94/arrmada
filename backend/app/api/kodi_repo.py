"""Dépôt Kodi (ADR-003 § 5) : `/kodi/repo/…`, réseau local, sans authentification.

Kodi ne sait pas envoyer d'en-tête d'authentification à un dépôt : ces
routes sont publiques mais limitées au réseau local. Elles ne contiennent
que le code de l'add-on (déjà public sur GitHub), aucun secret.

Chaque zip a aussi son empreinte `<zip>.sha256` (dépôt 1.1.0 : Kodi vérifie
le téléchargement et ne réutilise jamais un vieux zip de son cache).

Installation sur la TV, une seule fois :
  Gestionnaire de fichiers → Ajouter une source → http://<serveur>:8420/kodi/repo/
  Extensions → Installer depuis un fichier zip → cette source → repository.arrmada.zip
  Extensions → Installer depuis un dépôt → Dépôt ArrMada → ArrMada
"""

from __future__ import annotations

from html import escape

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.services import devices as devices_service
from app.services import kodi_repo

router = APIRouter(prefix="/kodi/repo", tags=["kodi-repo"])

_GET_HEAD = ["GET", "HEAD"]  # Kodi interroge souvent en HEAD avant de télécharger


def _root(request: Request):
    host = request.client.host if request.client else ""
    if not devices_service.is_lan_request(host, request.headers.get("X-Forwarded-For")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dépôt Kodi accessible en réseau local")
    root = kodi_repo.addon_root()
    if root is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Dépôt Kodi indisponible : dossier kodi-addon non monté (voir docker-compose.yml)",
        )
    return root


def _base_url(request: Request) -> str:
    """Adresse par laquelle la TV joint ArrMada (écrite dans le dépôt)."""
    return str(request.base_url).rstrip("/")


def _file(content: bytes | str, media_type: str, filename: str | None = None) -> Response:
    body = content.encode("utf-8") if isinstance(content, str) else content
    headers = {"Cache-Control": "no-cache"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=body, media_type=media_type, headers=headers)


@router.api_route("/", methods=_GET_HEAD)
async def listing(request: Request) -> Response:
    """Page « dossier » que Kodi sait parcourir (Installer depuis un fichier zip)."""
    root = _root(request)
    version = kodi_repo.addon_version(root)
    links = [
        "repository.arrmada.zip",
        f"{kodi_repo.ADDON_ID}/{kodi_repo.ADDON_ID}-{version}.zip",
        "addons.xml",
    ]
    # Kodi exige que le texte du lien soit identique à sa cible
    items = "\n".join(f'<li><a href="{escape(link)}">{escape(link)}</a></li>' for link in links)
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Dépôt Kodi ArrMada</title>"
        f"</head><body><h1>Dépôt Kodi ArrMada</h1><ul>\n{items}\n</ul></body></html>"
    )
    return _file(html, "text/html; charset=utf-8")


@router.get("/info.json")
async def info(request: Request) -> dict:
    """Versions servies (affichées dans la web app)."""
    root = _root(request)
    return {
        "addon_id": kodi_repo.ADDON_ID,
        "addon_version": kodi_repo.addon_version(root),
        "repository_version": kodi_repo.REPO_VERSION,
        "repo_url": f"{_base_url(request)}/kodi/repo/",
    }


@router.api_route("/addons.xml", methods=_GET_HEAD)
async def addons_xml(request: Request) -> Response:
    root = _root(request)
    return _file(kodi_repo.addons_xml(root, _base_url(request)), "application/xml")


@router.api_route("/addons.xml.md5", methods=_GET_HEAD)
async def addons_xml_md5(request: Request) -> Response:
    root = _root(request)
    return _file(kodi_repo.md5(kodi_repo.addons_xml(root, _base_url(request))), "text/plain")


_REPO_ZIP = f"{kodi_repo.REPO_ID}-{kodi_repo.REPO_VERSION}.zip"


@router.api_route("/repository.arrmada.zip", methods=_GET_HEAD)
@router.api_route(f"/{kodi_repo.REPO_ID}/{_REPO_ZIP}", methods=_GET_HEAD)
async def repository_zip(request: Request) -> Response:
    root = _root(request)
    return _file(kodi_repo.repository_zip(root, _base_url(request)), "application/zip", _REPO_ZIP)


@router.api_route(f"/{kodi_repo.REPO_ID}/{_REPO_ZIP}.sha256", methods=_GET_HEAD)
async def repository_zip_sha256(request: Request) -> Response:
    """Empreinte du zip du dépôt (Kodi la lit avant de le mettre à jour)."""
    root = _root(request)
    return _file(kodi_repo.sha256(kodi_repo.repository_zip(root, _base_url(request))), "text/plain")


@router.api_route(f"/{kodi_repo.REPO_ID}/icon.png", methods=_GET_HEAD)
async def repository_icon(request: Request) -> Response:
    root = _root(request)
    icon = root / kodi_repo.ADDON_ID / "resources" / "icon.png"
    if not icon.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return _file(icon.read_bytes(), "image/png")


@router.api_route(f"/{kodi_repo.ADDON_ID}/{{name:path}}", methods=_GET_HEAD)
async def addon_file(request: Request, name: str) -> Response:
    """Zip de la version en cours (et son empreinte), ou image déclarée dans addon.xml."""
    root = _root(request)
    version = kodi_repo.addon_version(root)
    if name == f"{kodi_repo.ADDON_ID}-{version}.zip":
        return _file(kodi_repo.addon_zip(root), "application/zip", name)
    if name == f"{kodi_repo.ADDON_ID}-{version}.zip.sha256":
        return _file(kodi_repo.sha256(kodi_repo.addon_zip(root)), "text/plain")
    # Liste blanche : seules les images déclarées (pas de « ../ » possible)
    if name in kodi_repo.addon_assets(root):
        path = root / kodi_repo.ADDON_ID / name
        media = "image/png" if name.endswith(".png") else "image/jpeg"
        return _file(path.read_bytes(), media)
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier absent du dépôt")
