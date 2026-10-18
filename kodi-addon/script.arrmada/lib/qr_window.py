# -*- coding: utf-8 -*-
"""Fenêtre « QR code vers le téléphone » (ADR-003 § 7, phase 3).

Mise en page : resources/skins/Default/1080i/script-arrmada-qr.xml.

Ce qui ne se fait pas sur la TV s'ouvre sur le téléphone : on vise le QR
code avec l'appareil photo et la bonne page de la web app s'ouvre (ou la
bande-annonce sur YouTube). Sur Android, un bouton l'ouvre aussi dans le
navigateur de la TV.

Le QR code est fabriqué par le serveur (`GET /api/qr`, seul à connaître
l'adresse de la web app) et enregistré dans special://temp : Kodi affiche
un fichier local, sans avoir à le télécharger lui-même.
"""

from __future__ import annotations

import base64
import binascii
import os
import threading

import xbmc
import xbmcgui
import xbmcvfs

import links_data
import ui_common as ui
from api import ArrMadaAPI

XML_FILE = "script-arrmada-qr.xml"

# Identifiants des boutons : DOIVENT correspondre au XML (vérifié par les tests).
BTN_BROWSER = 951
BTN_CLOSE = 952


def _save_png(url: str, png_b64: str) -> str:
    """Écrit l'image dans special://temp ; chemin du fichier, ou "" si illisible."""
    try:
        data = base64.b64decode(png_b64, validate=True)
    except (binascii.Error, ValueError):
        return ""
    if not data.startswith(b"\x89PNG"):
        return ""
    folder = xbmcvfs.translatePath("special://temp/")
    path = os.path.join(folder, links_data.qr_file_name(url))
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, path)  # Kodi ne lit jamais une image à moitié écrite
    return path


class QrWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._title = kwargs.get("title", "")
        self._text = kwargs.get("text", "")
        self._path = kwargs.get("path", "")
        self._youtube = kwargs.get("youtube", "")
        self._url = ""
        self._initialized = False

    def onInit(self):
        if self._initialized:
            return
        self._initialized = True
        self.setProperty("title", self._title)
        self.setProperty("text", self._text)
        self.setProperty("state", "loading")
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        response = ArrMadaAPI.get_qr(path=self._path, youtube=self._youtube)
        url = response.get("url") if isinstance(response, dict) else ""
        image = _save_png(url, response.get("png", "")) if url else ""
        if not image:
            message = response.get("message") if isinstance(response, dict) else ""
            self.setProperty("error", message or "QR code indisponible")
            self.setProperty("state", "error")
            ui.log("QR", f"échec : {message}", xbmc.LOGWARNING)
            return
        self._url = url
        self.setProperty("url", url)
        self.setProperty("qr", image)
        android = xbmc.getCondVisibility("System.Platform.Android")
        self.setProperty("can_open", "1" if android and links_data.android_open_url(url) else "")
        self.setProperty("state", "ready")

    def onAction(self, action):
        if action.getId() in ui.BACK_ACTIONS:
            self.close()

    def onClick(self, controlId):
        if controlId == BTN_CLOSE:
            self.close()
        elif controlId == BTN_BROWSER:
            command = links_data.android_open_url(self._url)
            if command:
                xbmc.executebuiltin(command)


def show_qr(title: str, text: str, path: str = "", youtube: str = "") -> None:
    """Ouvre la fenêtre QR (page de la web app `path`, ou vidéo YouTube `youtube`)."""
    window = QrWindow(
        XML_FILE,
        ui.ADDON.getAddonInfo("path"),
        "Default",
        "1080i",
        title=title,
        text=text,
        path=path,
        youtube=youtube,
    )
    try:
        window.doModal()
    finally:
        del window


def show_page(name: str) -> None:
    """Page de la web app décrite dans links_data.PAGES."""
    page = links_data.PAGES[name]
    show_qr(page.title, page.text, path=page.path)
