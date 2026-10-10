"""Liens de la TV vers la web app (ADR-003 § 7) : QR codes.

Ce qui ne se fait pas sur la TV (configuration, nettoyage, page complète d'un
titre…) reste dans la web app. La TV affiche alors un QR code : on le vise
avec le téléphone et la bonne page s'ouvre. Même principe pour une
bande-annonce quand Kodi n'a pas l'add-on YouTube.

Le serveur construit l'adresse (lui seul connaît celle de la web app :
`PUBLIC_WEB_URL`, ou l'adresse jointe par la TV avec le port 3420) et
renvoie l'image en base64 dans du JSON. L'add-on l'écrit dans un fichier
local : Kodi n'a pas à télécharger l'image lui-même, ce qu'il ferait sans
le jeton de la TV (impossible d'ajouter un en-tête aux images d'un skin).
"""

from __future__ import annotations

import base64
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_user
from app.api.devices import web_base_url
from app.services.devices import qr_png

router = APIRouter(prefix="/api/qr", tags=["links"])

# Chemin de la web app : lettres, chiffres, / _ - . et une requête simple.
# Pas de « // » (adresse d'un autre site) ni de schéma : on ne fabrique
# jamais de QR code vers un site inconnu.
_WEB_PATH = re.compile(r"/[A-Za-z0-9/_\-.]*(\?[A-Za-z0-9_\-.=&%]*)?")
_YOUTUBE_ID = re.compile(r"[A-Za-z0-9_-]{11}")
MAX_PATH = 300


def target_url(web_base: str, path: str | None = None, youtube: str | None = None) -> str:
    """Adresse encodée dans le QR code. ValueError si la demande est refusée."""
    if youtube:
        if not _YOUTUBE_ID.fullmatch(youtube):
            raise ValueError("Identifiant de vidéo YouTube invalide")
        return f"https://www.youtube.com/watch?v={youtube}"
    path = path or "/"
    if len(path) > MAX_PATH or "//" in path or not _WEB_PATH.fullmatch(path):
        raise ValueError("Chemin de la web app invalide")
    return f"{web_base}{path}"


@router.get("")
async def qr_code(
    request: Request,
    path: str | None = None,
    youtube: str | None = None,
    _user: dict = Depends(get_current_user),
) -> dict:
    """QR code vers une page de la web app (`path`) ou une vidéo YouTube (`youtube`).

    Réponse : `{"url": adresse encodée, "png": image PNG en base64}`.
    """
    try:
        url = target_url(web_base_url(request), path, youtube)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return {"url": url, "png": base64.b64encode(qr_png(url, scale=8)).decode("ascii")}
