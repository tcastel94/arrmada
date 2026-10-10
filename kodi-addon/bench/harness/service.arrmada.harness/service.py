# -*- coding: utf-8 -*-
"""Harnais du banc de test : pilote Kodi comme une télécommande et prend des captures.

Lancé automatiquement au démarrage de Kodi (add-on de type « service »), il
rejoue un parcours complet sur l'appli ArrMada (Accueil, Fiche média,
Téléchargements, Salon, Appairage, listes natives, widgets, temps réel),
puis quitte Kodi.
Variables d'environnement (posées par run.sh) : SHOT_DIR, MOCK_URL, PACE, DEMO_VIDEO.
"""

import json
import os
import urllib.request

import xbmc
import xbmcaddon
import xbmcvfs

MONITOR = xbmc.Monitor()
OUT = os.environ.get("SHOT_DIR", "/tmp")
MOCK = os.environ.get("MOCK_URL", "")
DEMO_VIDEO = os.environ.get("DEMO_VIDEO", "")
# PACE > 1 ralentit tout le parcours (vidéos de démonstration).
PACE = float(os.environ.get("PACE", "1") or 1)


def log(message):
    xbmc.log(f"[HARNESS] {message}", xbmc.LOGINFO)


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


def focus():
    return xbmc.getInfoLabel("System.CurrentControlID")


def run_plugin(action):
    xbmc.executebuiltin(f"RunPlugin(plugin://script.arrmada/?action={action})")


wait(8)  # accueil de Kodi chargé

# ── 0. Phase 3 : la TV s'est appairée toute seule avec l'ancien mot de passe ─
_device = xbmcvfs.translatePath("special://profile/addon_data/script.arrmada/device.json")
log(
    "migration : jeton "
    + ("présent" if os.path.exists(_device) else "ABSENT")
    + ", mot de passe "
    + ("effacé" if not xbmcaddon.Addon("script.arrmada").getSetting("api_key") else "ENCORE LÀ")
)

# ── 1. Ouverture depuis le menu de l'add-on (intro), accueil ────────────────
xbmc.executebuiltin("ActivateWindow(Videos,plugin://script.arrmada/,return)")
wait(4.0)
shot("00-menu-addon")
for _ in range(3):  # 1er élément = « .. » si Kodi affiche le dossier parent
    if xbmc.getInfoLabel("ListItem.Label") == "Accueil":
        break
    press("Down", 1, 0.5)
press("Select", 1, 0.1)
wait(0.6)
shot("01a-intro-logo")
wait(0.2)
shot("01b-intro-nom")
wait(5)
shot("02-accueil")

# ── 2. Rangée : focus, appui long, touche Lecture ──────────────────────────
press("Right", 3)
wait(1.2)
shot("03-focus-affiche")
press("ContextMenu")
wait(1.2)
shot("03b-actions-rapides")
press("Back")
press("PlayPause")
wait(1.2)
shot("03c-lecture-hors-mediatheque")
wait(2.5)

# ── 3. Fiche média : film (Monte-Cristo), puis série (Severance) ───────────
press("Select")  # OK sur l'affiche → fiche
wait(0.8)
shot("04a-fiche-ouverture")
wait(3.0)
shot("04b-fiche-film")
press("Down")
press("Right", 2)
wait(1.0)
shot("04c-fiche-casting")
press("Up")
press("Right")  # Lire → Bande-annonce
press("Select")
wait(1.5)
wait(1.5)  # QR code de la bande-annonce (phase 3)
shot("04d-bande-annonce-sans-youtube")
press("Back")  # ferme la fenêtre QR
wait(1.0)
press("Back")  # retour à l'accueil
wait(1.5)
press("Right")  # Severance (série)
press("Select")
wait(3.5)
shot("04e-fiche-serie")
press("Down")
press("Right")
wait(1.0)
shot("04f-fiche-saisons")
press("Back")
wait(1.5)

# ── 4. Téléchargements (bouton du bandeau) ─────────────────────────────────
press("Up")  # → Rechercher
press("Right")  # → Téléchargements
press("Select")
wait(3.0)
shot("05a-telechargements")
wait(6.0)  # 2e passage : débit estimé
press("Down", 4, 0.5)
wait(1.0)
shot("05b-telechargements-debit")
press("Up", 6, 0.4)  # → boutons du haut
press("Select")  # Tout mettre en pause
wait(3.0)
shot("05c-telechargements-pause")
press("Right")
press("Select")  # Tout reprendre
wait(2.0)
press("Back")
wait(1.5)

# ── 5. Salon (bouton du bandeau), sans lecture ─────────────────────────────
log(f"focus avant Salon = {focus()}")
press("Right")  # Téléchargements → Salon
press("Select")
wait(3.0)
shot("06a-salon")
press("Select", 3, 0.8)  # Vol + ×3
wait(3.5)
shot("06b-salon-volume")
press("Down")  # préréglages
press("Select")  # Salon
wait(3.5)
shot("06c-salon-prereglage")
press("Back")
wait(1.5)

# ── 6. Diagnostic puis fermeture ───────────────────────────────────────────
press("Right", 3)  # Salon → Actualiser → Diagnostic
press("Select")
wait(2.0)
shot("07-diagnostic")
press("Back")
wait(1.0)
press("Back")  # ferme l'accueil
wait(2.0)

# ── 6b. Appairage de la TV (le faux serveur valide au 3e poll, ~9 s) ───────
run_plugin("pair")
wait(2.0)
shot("07b-appairage-code")
wait(9.0)
shot("07c-appairage-ok")
wait(5.0)  # l'écran se ferme seul ; la suite utilise le jeton d'appareil

# ── 6c. Navigation native, widgets, temps réel (TV appairée) ───────────────
def open_list(query, name, settle=3.0):
    xbmc.executebuiltin(f"ActivateWindow(Videos,plugin://script.arrmada/{query},return)")
    wait(settle)
    if xbmc.getInfoLabel("ListItem.Label") == "..":
        press("Down", 1, 1.5)  # focus sur le 1er élément : affiche et synopsis visibles
    log(f"{name} : {xbmc.getInfoLabel('Container.NumItems')} éléments")
    shot(name)


open_list("", "13a-racine")
open_list("?action=list&feed=upcoming", "13b-calendrier")
open_list("?action=list&feed=foryou&sub=foryou", "13c-pour-toi")
open_list("?action=list&feed=missing", "13d-manquants")
press("ContextMenu")  # appui long : Fiche détaillée, Chercher une meilleure version
wait(1.0)
shot("13e-appui-long")
press("Back")
open_list("?action=widgets", "13f-widgets")
open_list("?action=list&feed=notifications", "13g-notifications")
# Import publié par le serveur : relevé dans les 5 s, notification à l'écran,
# puis flux concernés rafraîchis un par seconde (annoncés aux widgets par
# arrmada.reload une fois la série terminée)
before = xbmc.getInfoLabel("Window(Home).Property(arrmada.reload)")
IMPORT = (
    f"{MOCK}/__emit?type=new_import&event=Download&title=Gladiator%20II&quality=Remux-2160p"
    f"&size=68719476736&poster={MOCK}/img/poster-3.jpg"
)
urllib.request.urlopen(IMPORT).read()
for _ in range(24):  # la bulle, au plus 12 s
    wait(0.5)
    if xbmc.getCondVisibility("Window.IsVisible(notification)"):
        break
wait(0.8)  # fin de l'animation d'entrée de la bulle
shot("13h-temps-reel")
for _ in range(24):  # l'annonce aux widgets, au plus 12 s
    if xbmc.getInfoLabel("Window(Home).Property(arrmada.reload)") != before:
        break
    wait(0.5)
log(f"rechargement des widgets : {before or '(aucun)'} → {xbmc.getInfoLabel('Window(Home).Property(arrmada.reload)')}")
press("Back")
wait(1.0)
xbmc.executebuiltin("ActivateWindow(Home)")
wait(2.0)

# ── 6d. Phase 3 : QR code vers la web app, raccourcis (favoris Kodi) ──────
run_plugin("qr&page=home")
wait(3.0)
shot("14a-qr-web-app")
press("Back")
wait(1.0)
run_plugin("favourites")
wait(1.5)
shot("14b-favoris-ajoutes")
_favs = json.loads(
    xbmc.executeJSONRPC(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "Favourites.GetFavourites",
                    "params": {"properties": ["path"]}})
    )
).get("result", {}).get("favourites") or []
log(f"favoris : {[f.get('title') for f in _favs]}")
wait(6.0)  # la bulle disparaît
# Un favori lance l'écran comme une lecture (PlayMedia) : il doit s'ouvrir normalement
xbmc.executebuiltin('PlayMedia("plugin://script.arrmada/?action=salon")')
wait(4.0)
shot("14c-favori-salon")
log(f"favori Salon : fenêtre {xbmc.getInfoLabel('System.CurrentWindow')}")
press("Back")
wait(1.5)

# ── 6e. Films / Séries : toute la bibliothèque (1.9.0) ─────────────────────
open_list("?action=library&kind=movie", "15a-films")
open_list("?action=browse&kind=movie&view=all", "15b-films-a-z")
log(f"films, page 1 : dernier élément « {xbmc.getInfoLabel('Container.ListItemAbsolute(100).Label')} »")
open_list("?action=browse&kind=movie&view=all&page=2", "15c-films-page-2")
open_list("?action=genres&kind=movie", "15d-films-genres")
open_list("?action=browse&kind=series&view=all", "15e-series")
press("Back")
wait(1.0)

# ── 7. Réouverture (cache), panne serveur ──────────────────────────────────
run_plugin("home")
wait(1.2)
shot("08-reouverture-cache")

# ── 8. Lecture d'une vidéo + écran Salon par-dessus ────────────────────────
if DEMO_VIDEO and os.path.exists(DEMO_VIDEO):
    press("Back")
    wait(1.5)
    xbmc.Player().play(DEMO_VIDEO)
    wait(4.0)
    run_plugin("salon")
    wait(3.0)
    shot("09a-salon-lecture")
    press("Select")  # Lecture / Pause
    wait(1.5)
    shot("09b-salon-pause")
    press("Back")
    wait(1.0)
    # Phase 3 : un import pendant le film ne s'affiche pas…
    urllib.request.urlopen(IMPORT.replace("Gladiator%20II", "Wicked")).read()
    wait(7.0)
    log(f"bulle pendant le film : {xbmc.getCondVisibility('Window.IsVisible(notification)')}")
    xbmc.executebuiltin("PlayerControl(Stop)")
    # … mais un résumé « Pendant ta séance » apparaît à l'arrêt
    for _ in range(16):
        wait(0.5)
        if xbmc.getCondVisibility("Window.IsVisible(notification)"):
            break
    wait(0.8)
    shot("09c-resume-seance")
    wait(2.0)
    run_plugin("home")
    wait(1.5)

urllib.request.urlopen(f"{MOCK}/__down").read()
press("Up")
press("Right", 3)  # Rechercher → … → Actualiser
log(f"focus avant Actualiser = {focus()}")
press("Select")
wait(4.0)
shot("10-hors-ligne")
press("Back")
wait(1.5)

# ── 9. Panne ET aucun cache ────────────────────────────────────────────────
cache = xbmcvfs.translatePath("special://profile/addon_data/script.arrmada/cache/home.json")
if os.path.exists(cache):
    os.remove(cache)
run_plugin("home")
wait(4.0)
shot("11-hors-ligne-sans-cache")
log(f"focus = {focus()} (attendu : 401, Actualiser)")
press("Back")
wait(1.5)

# ── 10. Serveur qui répond mais refuse la TV (401) : pas « injoignable » ───
urllib.request.urlopen(f"{MOCK}/__deny").read()
run_plugin("home")
wait(4.0)
shot("12-tv-refusee")
log(f"titre de l'erreur : {xbmc.getInfoLabel('Window.Property(error_title)')}")
press("Back")
wait(1.5)

log("terminé")
xbmc.executebuiltin("Quit")
