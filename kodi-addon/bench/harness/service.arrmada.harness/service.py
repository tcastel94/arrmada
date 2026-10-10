# -*- coding: utf-8 -*-
"""Harnais du banc de test : pilote Kodi comme une télécommande et prend des captures.

Lancé automatiquement au démarrage de Kodi (add-on de type « service »), il
rejoue un parcours fixe sur l'écran « Accueil » d'ArrMada, puis quitte Kodi.
Variables d'environnement (posées par run.sh) : SHOT_DIR, MOCK_URL.
"""

import os
import urllib.request

import xbmc
import xbmcvfs

MONITOR = xbmc.Monitor()
OUT = os.environ.get("SHOT_DIR", "/tmp")
MOCK = os.environ.get("MOCK_URL", "")


def log(message):
    xbmc.log(f"[HARNESS] {message}", xbmc.LOGINFO)


# PACE > 1 ralentit tout le parcours (vidéos de démonstration).
PACE = float(os.environ.get("PACE", "1") or 1)


def wait(seconds):
    return MONITOR.waitForAbort(seconds * PACE)


def shot(name):
    log(f"capture {name}")
    xbmc.executebuiltin(f"TakeScreenshot({OUT}/{name}.png,sync)")
    wait(1.0)


def press(action, times=1, pause=0.7):
    for _ in range(times):
        xbmc.executebuiltin(f"Action({action})")
        wait(pause)


def open_home():
    xbmc.executebuiltin("RunPlugin(plugin://script.arrmada/?action=home)")


wait(8)  # accueil de Kodi chargé

# 1. Ouverture depuis le menu de l'add-on, comme à la télécommande
xbmc.executebuiltin("ActivateWindow(Videos,plugin://script.arrmada/,return)")
wait(4.0)
shot("00-menu-addon")
for _ in range(3):  # 1er élément = « .. » si Kodi affiche le dossier parent
    if "Accueil ArrMada" in xbmc.getInfoLabel("ListItem.Label"):
        break
    press("Down", 1, 0.5)
log(f"entrée sélectionnée : {xbmc.getInfoLabel('ListItem.Label')}")
press("Select", 1, 0.1)
wait(0.6)
shot("01a-intro-logo")  # intro : le logo se construit
wait(0.2)
shot("01b-intro-nom")  # intro : le nom et l'accroche montent
wait(5)
shot("02-accueil")

# 2. Focus et navigation
press("Right", 3)
wait(1.5)
shot("03-focus-affiche")
press("Right", 7, 0.5)
wait(1.5)
shot("04-sans-affiche")

# 2 bis. Télécommande : appui long sur OK (= menu contextuel) et touche Lecture
press("ContextMenu")
wait(1.2)
shot("04b-actions-rapides")
press("Back")
press("PlayPause")
wait(1.2)
shot("04c-lecture-hors-mediatheque")  # titre absent de la médiathèque Kodi du banc
wait(2.5)

press("Up")
wait(1.0)
shot("05-boutons")
press("Right", 2)  # Rechercher → Actualiser → Diagnostic
press("Select")
wait(2.0)
shot("06-diagnostic")
press("Back")
wait(1.0)
shot("07-retour")
press("Left", 2)  # → Rechercher
press("Select")
wait(1.5)
shot("07b-recherche-clavier")
press("Back")
wait(1.0)
press("Back")
wait(2.0)

# 3. Réouverture : affichage immédiat depuis le cache
open_home()
wait(1.2)
shot("08-reouverture-cache")

# 4. Panne du serveur pendant l'affichage
urllib.request.urlopen(f"{MOCK}/__down").read()
press("Up")
press("Right")  # Rechercher → Actualiser
press("Select")
wait(4.0)
shot("09-hors-ligne")
press("Back")
wait(1.5)

# 5. Panne du serveur ET aucun cache (première ouverture hors ligne)
cache = xbmcvfs.translatePath("special://profile/addon_data/script.arrmada/cache/home.json")
if os.path.exists(cache):
    os.remove(cache)
open_home()
wait(4.0)
shot("10-hors-ligne-sans-cache")
log(f"focus = {xbmc.getInfoLabel('System.CurrentControlID')} (attendu : 401, Actualiser)")
press("Back")
wait(1.5)

log("terminé")
xbmc.executebuiltin("Quit")
