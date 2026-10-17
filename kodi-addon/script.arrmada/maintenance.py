# -*- coding: utf-8 -*-
"""ArrMada — NAS Maintenance & Cleanup Assistant for Kodi.

Provides TV-friendly triggers for cleaning orphan files, empty directories,
and synchronizing/cleaning the Kodi media database.
"""

from __future__ import annotations

import sys
import os
import xbmcgui

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from api import ArrMadaAPI
from kodi_helper import show_notification


def show_maintenance_menu():
    """Main maintenance assistant dialog."""
    menu = [
        "[NETTOYAGE]  Supprimer dossiers vides et fichiers orphelins",
        "[SCAN]       Forcer la mise a jour de la mediatheque Kodi",
        "[NETTOYAGE]  Nettoyer la base de donnees Kodi (Clean DB)",
    ]

    while True:
        choice = xbmcgui.Dialog().select("ArrMada -- Maintenance du NAS", menu)
        if choice < 0:
            break

        if choice == 0:
            _run_orphan_clean()
        elif choice == 1:
            _run_kodi_scan()
        elif choice == 2:
            _run_kodi_clean()


def _run_orphan_clean():
    confirm = xbmcgui.Dialog().yesno(
        "Nettoyage NAS ArrMada",
        "Voulez-vous lancer le nettoyage automatique des dossiers vides et fichiers orphelins dans les telechargements ?",
        yeslabel="Nettoyer",
        nolabel="Annuler"
    )
    if not confirm:
        return

    pd = xbmcgui.DialogProgress()
    pd.create("ArrMada", "Nettoyage du stockage en cours...")
    pd.update(50)

    try:
        res = ArrMadaAPI.clean_orphans()
    except Exception as exc:
        res = {"status": "error", "message": str(exc)}
    finally:
        pd.close()

    if res.get("status") == "ok":
        msg = res.get("message", "Nettoyage termine avec succes !")
        xbmcgui.Dialog().ok("ArrMada - Maintenance", msg)
    else:
        err = res.get("message", "Erreur lors du nettoyage")
        show_notification("ArrMada", err, is_error=True)


def _run_kodi_scan():
    show_notification("ArrMada", "Scan de la mediatheque lance...", is_error=False)
    ArrMadaAPI.trigger_sync()


def _run_kodi_clean():
    confirm = xbmcgui.Dialog().yesno(
        "Nettoyage Kodi",
        "Voulez-vous supprimer de Kodi les entrees de fichiers qui n'existent plus sur le NAS ?",
        yeslabel="Nettoyer DB",
        nolabel="Annuler"
    )
    if not confirm:
        return

    show_notification("ArrMada", "Nettoyage de la base Kodi en cours...", is_error=False)
    ArrMadaAPI.trigger_clean()


if __name__ == "__main__":
    show_maintenance_menu()
