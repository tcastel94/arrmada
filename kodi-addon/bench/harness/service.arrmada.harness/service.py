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
import xbmcgui
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


def shell_open():
    return xbmc.getInfoLabel("Window(Home).Property(arrmada.shell)") == "1"


def leave_shell(name=None):
    """Retour sur l'accueil ArrMada → « Quitter ? » → Interface Kodi (retour auto suspendu)."""
    press("Back")
    wait(1.2)
    if name:
        shot(name)
    press("Down")  # « Rester dans ArrMada » → « Interface Kodi »
    press("Select")
    wait(2.0)


# ── 0a. ADR-004 phase 4.2 : Kodi démarre sur l'accueil ArrMada ─────────────
log(f"démarrage : accueil ArrMada {'ouvert' if shell_open() else 'NON OUVERT'}")
shot("00a-demarrage-sur-arrmada")
if shell_open():
    leave_shell("00b-quitter")  # la suite du parcours se fait dans l'interface Kodi
    log(
        "après « Interface Kodi » : retour automatique "
        + ("suspendu" if xbmc.getInfoLabel("Window(Home).Property(arrmada.shell_off)") else "ACTIF")
        + f", accueil ArrMada {'ouvert' if shell_open() else 'fermé'}"
    )

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
for _ in range(4):  # 1er élément = « .. » si Kodi affiche le dossier parent
    if xbmc.getInfoLabel("ListItem.Label") == "Tableau de bord":  # l'ancien Accueil
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


# ── 6f. ADR-004 phase 4.1 : médiathèque Kodi, écran Série, reprise ─────────
def rpc(method, params=None):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
    return json.loads(xbmc.executeJSONRPC(json.dumps(request))).get("result") or {}


def player_state():
    props = rpc("Player.GetProperties", {"playerid": 1, "properties": ["time", "position"]})
    t = props.get("time") or {}
    queue = rpc("Playlist.GetItems", {"playlistid": 1, "properties": ["season", "episode"]})
    codes = [f"S{i.get('season'):02d}E{i.get('episode'):02d}" for i in queue.get("items") or []]
    return f"{t.get('minutes', 0)}:{t.get('seconds', 0):02d}", codes


rpc("VideoLibrary.Scan")
wait(2.0)
for _ in range(60):
    if not xbmc.getCondVisibility("Library.IsScanningVideo"):
        break
    wait(1.0)
shows = rpc("VideoLibrary.GetTVShows", {"properties": ["title"]}).get("tvshows") or []
movies = rpc("VideoLibrary.GetMovies", {"properties": ["title"]}).get("movies") or []
log(f"médiathèque : {len(shows)} série(s), {len(movies)} film(s)")
if shows and movies:
    SID, MID = shows[0]["tvshowid"], movies[0]["movieid"]
    eps = rpc("VideoLibrary.GetEpisodes", {"tvshowid": SID, "properties": ["season", "episode"]})
    BYK = {(e["season"], e["episode"]): e["episodeid"] for e in eps.get("episodes") or []}
    # Situation de départ : S01E01 à E03 vus, S01E04 commencé (0:30), film commencé (0:40)
    for key, eid in BYK.items():
        state = {"episodeid": eid, "playcount": 1 if key in ((1, 1), (1, 2), (1, 3)) else 0}
        state["resume"] = {"position": 30.0 if key == (1, 4) else 0.0, "total": 90.0}
        state["lastplayed"] = "2026-10-10 21:00:00" if key <= (1, 4) else ""
        rpc("VideoLibrary.SetEpisodeDetails", state)
    rpc(
        "VideoLibrary.SetMovieDetails",
        {
            "movieid": MID,
            "playcount": 0,
            "resume": {"position": 40.0, "total": 90.0},
            "lastplayed": "2026-10-09 20:00:00",
        },
    )

    # Kodi rafraîchit la liste affichée après ces changements, et refuse
    # d'ouvrir une fenêtre pendant ce temps : on attend sur l'accueil.
    xbmc.executebuiltin("ActivateWindow(Home)")
    wait(3.0)

    # Fiche du film : le bouton « Lire » devient « Reprendre à 0:40 »
    run_plugin("detail&kind=movie&arr_id=103&title=Le%20Comte%20de%20Monte-Cristo&year=2024")
    wait(4.0)
    log(f"fiche film : bouton « {xbmc.getInfoLabel('Window.Property(play_label)')} »")
    shot("16a-fiche-film-reprendre")
    press("Back")
    wait(1.5)

    # Écran Série : saison et épisode « à suivre » déjà sélectionnés
    run_plugin(f"series&tvshowid={SID}")
    wait(4.0)
    log(
        f"écran Série : « {xbmc.getInfoLabel('Window.Property(play_label)')} », "
        f"{xbmc.getInfoLabel('Window.Property(meta)')}"
    )
    shot("16b-serie")
    press("Down")  # saisons
    press("Down")  # épisodes
    wait(1.0)
    log(f"épisode sélectionné : {xbmc.getInfoLabel('Container(300).ListItem.Property(code)')}")
    shot("16c-serie-episodes")
    press("Up")  # saisons
    press("Right")  # saison 2
    wait(1.5)
    log(f"saison 2 : {xbmc.getInfoLabel('Container(300).NumItems')} épisodes")
    shot("16d-serie-saison-2")
    press("Left")
    press("Down")
    press("ContextMenu")  # appui long : depuis le début, vu / non vu, toute la saison
    wait(1.2)
    shot("16e-serie-appui-long")
    press("Back")
    wait(0.8)
    press("Up", 2)  # → « Reprendre S01E04 »
    press("Select")
    wait(1.2)
    shot("16f-reprendre-ou-debut")
    press("Select")  # Reprendre à 0:30
    wait(6.0)
    position, queue = player_state()
    log(f"lecture : position {position}, liste de lecture {queue}")
    shot("16g-lecture-reprise")
    xbmc.executebuiltin("PlayerControl(Stop)")
    wait(3.0)
    shot("16h-serie-apres-lecture")
    log(f"après lecture : « {xbmc.getInfoLabel('Window.Property(play_label)')} »")
    press("Back")
    wait(1.5)

    # Rangée « Reprendre » (dossier et widget SiLVO)
    open_list("?action=continue", "16i-reprendre")
    labels = [
        xbmc.getInfoLabel(f"Container.ListItemAbsolute({i}).Label")
        for i in range(int(xbmc.getInfoLabel("Container.NumItems") or 0) + 1)
    ]
    log("reprendre : " + " | ".join(label for label in labels if label and label != ".."))
    press("Back")
    wait(1.0)


# ── 6g. ADR-004 phase 4.2 : accueil média, grille, retour automatique ──────
def counts():
    return ", ".join(
        f"{name} {xbmc.getInfoLabel(f'Container({cid}).NumItems') or 0}"
        for name, cid in (
            ("reprendre", 610),
            ("applis", 650),
            ("ajouts", 620),
            ("pour toi", 630),
            ("bientôt", 640),
        )
    )


xbmc.executebuiltin("ActivateWindow(Home)")
wait(2.0)
run_plugin("shell")
wait(5.0)
log(f"accueil média : {counts()} ; en-tête « {xbmc.getInfoLabel('Window.Property(hero_title)')} »")
shot("17a-accueil-media")
press("Down")  # rangée suivante
wait(1.5)
log(f"rangée 2 : focus {focus()}, en-tête « {xbmc.getInfoLabel('Window.Property(hero_title)')} »")
shot("17b-accueil-rangee-2")
press("Up", 3, 0.6)  # jusqu'au menu
log(f"menu : focus {focus()}")
press("Right")  # Accueil → Films
press("Select")
wait(4.0)
log(f"grille Films : {xbmc.getInfoLabel('Window.Property(status)')}, focus {focus()}")
shot("17c-grille-films")
press("Down", 13, 0.35)  # 13e ligne (n° 91 sur 100) : la page 2 se charge d'avance
wait(3.0)
log(
    f"grille Films après défilement : {xbmc.getInfoLabel('Window.Property(status)')}, "
    f"sur « {xbmc.getInfoLabel('Container(300).ListItem.Label')} » "
    f"(n° {xbmc.getInfoLabel('Container(300).CurrentItem')})"
)
shot("17d-grille-page-2")
press("Up", 16, 0.25)
press("Up")  # → onglets
press("Right")  # Ajoutés récemment
press("Select")
wait(3.0)
log(f"onglet : {xbmc.getInfoLabel('Window.Property(subtitle)')}")
shot("17e-grille-recents")
press("Back")
wait(1.5)
press("Right")  # Films → Séries
press("Select")
wait(4.0)
press("Right")  # Arcane → Severance (A à Z)
wait(0.8)
shot("17f-grille-series")
press("Select")  # Severance est dans la médiathèque Kodi : écran Série
wait(4.0)
log(f"OK sur « Severance » : « {xbmc.getInfoLabel('Window.Property(play_label)')} »")
shot("17g-grille-vers-serie")
press("Back")
wait(1.0)
press("Back")
wait(1.5)
leave_shell("17h-quitter")
log(f"après « Interface Kodi » : accueil ArrMada {'ouvert' if shell_open() else 'fermé'}")
# Retour automatique : l'accueil de Kodi s'affiche → le service rouvre ArrMada
xbmcgui.Window(10000).clearProperty("arrmada.shell_off")
xbmc.executebuiltin("ActivateWindow(Home)")
for _ in range(16):
    wait(0.5)
    if shell_open():
        break
wait(2.0)
log(f"retour automatique : accueil ArrMada {'rouvert' if shell_open() else 'NON ROUVERT'}")
shot("17i-retour-automatique")
leave_shell()  # la suite du parcours se fait dans l'interface Kodi


# ── 6h. ADR-004 phase 4.3 : Applis & sources, recherche dans la grille ─────
def apps_state():
    return (
        f"onglet « {xbmc.getInfoLabel('Container(200).ListItem.Label')} », "
        f"titre « {xbmc.getInfoLabel('Window.Property(title)')} », "
        f"chemin « {xbmc.getInfoLabel('Window.Property(crumb)')} », "
        f"{xbmc.getInfoLabel('Window.Property(layout)')} : "
        f"{xbmc.getInfoLabel('Container(300).NumItems') or 0} tuile(s), "
        f"{xbmc.getInfoLabel('Container(400).NumItems') or 0} ligne(s), focus {focus()}, "
        f"message « {xbmc.getInfoLabel('Window.Property(message)')} »"
    )


def labels_of(control):
    count = int(xbmc.getInfoLabel(f"Container({control}).NumItems") or 0)
    return [
        xbmc.getInfoLabel(f"Container({control}).ListItemAbsolute({i}).Label") for i in range(count)
    ]


def playing():
    """Ce que lit Kodi : « vidéo <fichier> » ou « chaîne « nom » » (sinon « rien »)."""
    item = rpc("Player.GetItem", {"playerid": 1, "properties": ["file"]}).get("item") or {}
    if item.get("type") == "channel":
        return f"chaîne « {item.get('label')} »"
    player = xbmc.Player()
    if player.isPlayingVideo():
        return f"vidéo {player.getPlayingFile()}"
    return "rien"


def wait_loaded(seconds=8.0):
    for _ in range(int(seconds / 0.5)):
        if not xbmc.getInfoLabel("Window.Property(loading)"):
            break
        wait(0.5)
    wait(1.0)


xbmc.executebuiltin("ActivateWindow(Home)")
wait(2.0)
run_plugin("shell")
wait(5.0)
log(f"accueil média (4.3) : {counts()}")
log(f"tes applis : {labels_of(650)}")
xbmc.executebuiltin("SetFocus(650)")
wait(1.5)
log(f"rangée Tes applis : focus {focus()}, en-tête « {xbmc.getInfoLabel('Window.Property(hero_title)')} »")
shot("18a-accueil-tes-applis")
xbmc.executebuiltin("SetFocus(404)")  # menu → Applis
wait(0.8)
log(f"menu : focus {focus()}")
press("Select")
wait(2.0)
wait_loaded()
log(f"Applis : {apps_state()} ; tuiles {labels_of(300)}")
shot("18b-applis-video")
press("Select")  # Banc TV (faux add-on) : son contenu s'affiche dans ArrMada
wait_loaded()
log(f"dans l'add-on : {apps_state()} ; {labels_of(400)}")
shot("18c-addon-racine")
press("Select")  # Concerts
wait_loaded()
press("Down")
wait(1.0)
log(f"Concerts : {apps_state()} ; {labels_of(400)}")
shot("18d-addon-videos")
press("ContextMenu")
wait(1.2)
shot("18e-appui-long")
press("Back")
wait(0.8)
press("Select")  # lecture de « Festival d'été » (résolue par l'add-on)
wait(6.0)
log(f"lecture depuis l'add-on : {playing()}")
shot("18f-lecture-addon")
xbmc.executebuiltin("PlayerControl(Stop)")
wait(3.0)
log(f"après lecture : {apps_state()}")
press("Back", 2, 1.0)  # Concerts → racine de l'add-on → onglets
wait_loaded()
log(f"retour : {apps_state()}")
press("Up")  # onglets
press("Right")  # TV en direct
press("Select")
wait_loaded(12.0)
log(f"TV en direct : {apps_state()} ; {labels_of(400)}")
log(f"programme : {xbmc.getInfoLabel('Container(400).ListItem.Label2')}")
shot("18g-tv-en-direct")
press("Select")  # 1re chaîne
wait(6.0)
log(f"chaîne : {playing()}")
shot("18h-chaine")
xbmc.executebuiltin("PlayerControl(Stop)")
wait(3.0)
press("Up")
press("Right", 2)  # Musique → Dossiers
press("Select")
wait_loaded()
log(f"Dossiers : {apps_state()} ; {labels_of(300)}")
shot("18i-dossiers")
press("Right", 2)  # Vidéos perso (banc)
press("Select")
wait_loaded()
log(f"vidéos perso : {apps_state()} ; {labels_of(400)}")
shot("18j-videos-perso")
press("Back")
wait(1.0)
press("Up")
press("Right")  # Favoris
press("Select")
wait_loaded()
log(f"Favoris : {apps_state()} ; {labels_of(300)}")
shot("18k-favoris")
press("Back")  # ferme l'écran : retour à l'accueil
wait(1.5)
xbmc.executebuiltin("SetFocus(406)")  # menu → Rechercher
wait(0.8)
press("Select")
wait(2.0)
rpc("Input.SendText", {"text": "dune", "done": True})
wait(5.0)
log(
    f"recherche : {xbmc.getInfoLabel('Window.Property(subtitle)')}, "
    f"{xbmc.getInfoLabel('Window.Property(status)')}, {labels_of(300)}"
)
shot("18l-recherche")
press("Back")
wait(1.5)
xbmc.executebuiltin("SetFocus(650)")  # rangée Tes applis → Banc TV
wait(1.0)
press("Select")
wait_loaded()
log(f"tuile de l'accueil : {apps_state()}")
shot("18m-tuile-addon")
press("Back")  # racine de l'add-on : l'écran se ferme, retour à l'accueil
wait(1.5)
log(f"Retour depuis la tuile : accueil ArrMada {'ouvert' if shell_open() else 'fermé'}, focus {focus()}")
leave_shell()

# ── 6i. ADR-004 phase 4.4 : vu partagé, épisodes manquants, épisode suivant ─
def watch_posts():
    return json.loads(urllib.request.urlopen(f"{MOCK}/__watch").read())


def describe(state):
    code = (
        f" S{int(state.get('season') or 0):02d}E{int(state.get('episode') or 0):02d}"
        if state.get("media_type") == "episode"
        else ""
    )
    what = "vu" if state.get("watched") else f"reprise {state.get('position')} s"
    return f"{state.get('title') or state.get('id')}{code} ({what})"


def episode_state(season, episode):
    details = rpc(
        "VideoLibrary.GetEpisodeDetails",
        {"episodeid": BYK[(season, episode)], "properties": ["playcount", "resume", "lastplayed"]},
    ).get("episodedetails") or {}
    return details.get("playcount"), int((details.get("resume") or {}).get("position") or 0)


if shows and movies:
    # 1. Ce que cette TV a déposé depuis le début du banc (premier passage + gestes)
    posts = watch_posts()["posts"]
    merged = sum(len(p["states"]) for p in posts if p["merge"])
    direct = [describe(s) for p in posts if not p["merge"] for s in p["states"]]
    log(f"vu partagé : premier passage {merged} état(s) en fusion ; en direct : {direct}")

    # 2. Une « autre TV » finit S01E07 et s'arrête à 0:50 du film
    urllib.request.urlopen(
        f"{MOCK}/__watch_push?season=1&episode=7&watched=1"
        "&last_played=2026-10-11%2020:00:00&title=Severance"
    ).read()
    urllib.request.urlopen(
        f"{MOCK}/__watch_push?media_type=movie&id_type=tmdb&id=1084736&position=50&total=90"
        "&title=Le%20Comte%20de%20Monte-Cristo"
    ).read()
    for _ in range(30):
        wait(0.5)
        if episode_state(1, 7)[0] == 1:
            break
    wait(1.0)
    movie = rpc(
        "VideoLibrary.GetMovieDetails", {"movieid": MID, "properties": ["resume"]}
    ).get("moviedetails") or {}
    log(
        f"vu partagé : S01E07 vu sur l'autre TV → ici playcount {episode_state(1, 7)[0]} ; "
        f"film repris à {int((movie.get('resume') or {}).get('position') or 0)} s ici"
    )

    # 3. Épisodes manquants (Sonarr) dans l'écran Série
    run_plugin(f"series&tvshowid={SID}")
    wait(5.0)
    press("Down")  # saisons
    press("Right")  # saison 2
    wait(1.0)
    press("Down")  # épisodes
    log(
        f"écran Série : {xbmc.getInfoLabel('Container(200).NumItems')} saison(s), "
        f"saison 2 : {xbmc.getInfoLabel('Container(300).NumItems')} épisode(s)"
    )
    press("Right", 5)  # S02E06 : diffusé, pas sur le NAS
    wait(1.0)
    log(
        f"S02E06 : « {xbmc.getInfoLabel('Container(300).ListItem.Property(badge)')} » "
        f"{xbmc.getInfoLabel('Container(300).ListItem.Property(status)')}"
    )
    shot("19a-serie-manquant")
    press("Select")  # « Lancer une recherche dans Sonarr ? »
    wait(1.2)
    shot("19b-chercher-sonarr")
    press("Back")
    wait(0.8)
    press("Right", 2)  # S02E08 : à venir
    wait(1.0)
    log(f"S02E08 : {xbmc.getInfoLabel('Container(300).ListItem.Property(status)')}")
    shot("19c-serie-a-venir")
    press("Up")
    press("Right")  # saison 3 (annoncée, sans date)
    wait(1.0)
    log(f"saison 3 : {xbmc.getInfoLabel('Container(200).ListItem.Label2')}")
    press("Back")
    wait(1.5)

    # 4. Épisode suivant : S01E05 lancé seul, encart à 20 s de la fin
    def seek(seconds):
        rpc("Player.Seek", {"playerid": 1, "value": {"time": {
            "hours": 0, "minutes": seconds // 60, "seconds": seconds % 60, "milliseconds": 0}}})

    def wait_upnext(seconds=25.0):
        for _ in range(int(seconds * 2)):
            wait(0.5)
            if xbmc.getInfoLabel("Window(Home).Property(arrmada.upnext_open)") == "1":
                return True
        return False

    rpc("Player.Open", {"item": {"episodeid": BYK[(1, 5)]}, "options": {"resume": False}})
    wait(4.0)
    seek(64)
    opened = wait_upnext()
    wait(1.5)
    position, queue = player_state()
    log(f"épisode suivant : encart {'ouvert' if opened else 'ABSENT'} à {position}, file {queue}")
    shot("19d-episode-suivant")
    press("Select")  # Lancer maintenant
    wait(4.0)
    log(
        f"lancer maintenant : lecture de S{xbmc.getInfoLabel('VideoPlayer.Season')}"
        f"E{xbmc.getInfoLabel('VideoPlayer.Episode')}, S01E05 playcount {episode_state(1, 5)[0]}"
    )
    seek(64)
    opened = wait_upnext()
    wait(1.0)
    press("Right")
    press("Select")  # Annuler
    wait(1.5)
    position, queue = player_state()
    log(f"annuler : encart {'vu' if opened else 'ABSENT'}, file restante {queue}")
    shot("19e-annuler")
    for _ in range(60):
        wait(0.5)
        if not xbmc.Player().isPlayingVideo():
            break
    wait(5.0)  # dépôt de l'état 3 s après la fin
    log(f"fin de l'épisode : lecture {'arrêtée' if not xbmc.Player().isPlayingVideo() else 'CONTINUE'}")
    last = [describe(s) for p in watch_posts()["posts"] if not p["merge"] for s in p["states"]]
    log(f"vu partagé : derniers dépôts {last[-3:]}")
    xbmc.executebuiltin("ActivateWindow(Home)")
    wait(2.0)


# ── 6j. ADR-004 phase 4.5 : panneau pendant le film (appui long sur OK) ─────
PANEL = os.environ.get("BENCH_PANEL", "")


def panel_open():
    return xbmc.getInfoLabel("Window(Home).Property(arrmada.player_open)") == "1"


def panel_state():
    props = rpc(
        "Player.GetProperties",
        {"playerid": 1, "properties": ["currentaudiostream", "currentsubtitle",
                                       "subtitleenabled", "subtitles", "time"]},
    )  # fmt: skip
    audio = (props.get("currentaudiostream") or {}).get("language", "?")
    sub = (props.get("currentsubtitle") or {}).get("language", "?")
    t = props.get("time") or {}
    return (
        f"audio {audio}, sous-titres {sub if props.get('subtitleenabled') else 'off'} "
        f"({len(props.get('subtitles') or [])} pistes), à {t.get('minutes', 0)}:{t.get('seconds', 0):02d}"
    )


keymap = xbmcvfs.translatePath("special://profile/keymaps/arrmada.xml")
log(f"raccourci du panneau : fichier de touches {'posé' if xbmcvfs.exists(keymap) else 'ABSENT'}")
if PANEL and os.path.exists(PANEL):
    rpc("Player.Open", {"item": {"file": PANEL}})
    for _ in range(30):  # Kodi cherche une sortie son quelques secondes (pas de carte)
        wait(0.5)
        if xbmc.Player().isPlayingVideo() and not xbmc.getCondVisibility("Window.IsActive(busydialog)"):
            break
    wait(3.0)
    log(f"film du panneau : {panel_state()}")
    # Appui long sur OK pendant la lecture (fichier de touches posé par le service)
    rpc("Input.ButtonEvent", {"button": "return", "keymap": "KB", "holdtime": 1200})
    for _ in range(12):
        wait(0.5)
        if panel_open():
            break
    via = "appui long"
    if not panel_open():
        via = "RunPlugin (appui long non simulable ici)"
        run_plugin("player")
        for _ in range(12):
            wait(0.5)
            if panel_open():
                break
    wait(1.0)
    sections = [
        f"{xbmc.getInfoLabel(f'Container(200).ListItemAbsolute({i}).Label')}"
        f" ({xbmc.getInfoLabel(f'Container(200).ListItemAbsolute({i}).Label2')})"
        for i in range(int(xbmc.getInfoLabel("Container(200).NumItems") or 0))
    ]
    log(f"panneau {'ouvert' if panel_open() else 'ABSENT'} par {via} : {sections}")
    shot("20a-panneau-audio")
    press("Right")  # choix de la section Audio
    press("Down")  # 2e piste : français
    press("Select")
    wait(1.5)
    log(f"audio changé : {panel_state()}")
    press("Left")
    press("Down")  # Sous-titres
    wait(0.8)
    shot("20b-panneau-sous-titres")
    press("Right")
    press("Down")  # 1re piste (anglais)
    press("Select")
    wait(1.5)
    log(f"sous-titres choisis : {panel_state()}")
    press("Down", 2)  # → « Chercher en français avec Bazarr »
    log(f"choix : {xbmc.getInfoLabel('Container(300).ListItem.Label')}")
    press("Select")  # le panneau se ferme, Bazarr (faux) cherche
    wait(2.0)
    log(f"après « Chercher » : panneau {'ENCORE OUVERT' if panel_open() else 'fermé'}")
    # Le faux Bazarr dépose le fichier à côté de la vidéo, comme le vrai
    with open(os.path.join(os.path.dirname(PANEL), "Panneau.fr.srt"), "w", encoding="utf-8") as srt:
        srt.write("1\n00:00:00,000 --> 00:03:00,000\nSous-titres Bazarr (banc)\n")
    for _ in range(20):
        wait(0.5)
        if "Panneau.fr.srt" in json.dumps(rpc(
            "Player.GetProperties", {"playerid": 1, "properties": ["currentsubtitle"]}
        )):  # fmt: skip
            break
    wait(1.0)
    current = rpc("Player.GetProperties", {"playerid": 1, "properties": ["currentsubtitle"]})
    log(f"Bazarr : sous-titres chargés → {(current.get('currentsubtitle') or {}).get('name', '?')} ; {panel_state()}")
    shot("20c-sous-titres-bazarr")
    # Ampli et chapitres
    run_plugin("player")
    for _ in range(12):
        wait(0.5)
        if panel_open():
            break
    wait(1.5)  # l'ampli arrive par le réseau
    press("Down", 2)  # Ampli
    wait(0.8)
    shot("20d-panneau-ampli")
    before = json.loads(urllib.request.urlopen(f"{MOCK}/api/yamaha/state").read())
    press("Right")
    press("Down")  # Volume +
    press("Select")
    wait(2.0)
    after = json.loads(urllib.request.urlopen(f"{MOCK}/api/yamaha/state").read())
    vol = [((d.get("devices") or [{}])[0]).get("volume_pct") for d in (before, after)]
    log(f"ampli : volume {vol[0]} % → {vol[1]} %")
    press("Left")
    press("Down")  # Lecture
    wait(0.8)
    press("Right")
    log(f"lecture : {xbmc.getInfoLabel('Container(300).ListItem.Label')} ({xbmc.getInfoLabel('Container(300).ListItem.Label2')})")
    shot("20e-panneau-lecture")
    position = panel_state()
    press("Select")  # Chapitre suivant
    wait(2.0)
    log(f"chapitre suivant : {position} → {panel_state()}")
    run_plugin("player")
    for _ in range(12):
        wait(0.5)
        if panel_open():
            break
    press("Back")
    wait(1.0)
    log(
        f"Retour : panneau {'ENCORE OUVERT' if panel_open() else 'fermé'}, "
        f"film {'en lecture' if xbmc.Player().isPlayingVideo() else 'ARRÊTÉ'}"
    )
    xbmc.executebuiltin("PlayerControl(Stop)")
    wait(2.0)
    xbmc.executebuiltin("ActivateWindow(Home)")
    wait(2.0)
else:
    log("vidéo du panneau absente (ffmpeg manquant ?) : section 4.5 sautée")


# ── 6k. 1.17 : « Passer l'intro » (chapitres nommés), sous-titres FR automatiques
INTRO_EPISODE = os.environ.get("BENCH_INTRO_EPISODE", "")


def skip_open():
    return xbmc.getInfoLabel("Window(Home).Property(arrmada.skip_open)") == "1"


def wait_skip(seconds=12.0):
    for _ in range(int(seconds * 2)):
        wait(0.5)
        if skip_open():
            return True
    return False


def chapter_now():
    t = rpc("Player.GetProperties", {"playerid": 1, "properties": ["time"]}).get("time") or {}
    return (
        f"« {xbmc.getInfoLabel('Player.ChapterName')} » "
        f"({xbmc.getInfoLabel('Player.Chapter')}/{xbmc.getInfoLabel('Player.ChapterCount')}) "
        f"à {t.get('minutes', 0)}:{t.get('seconds', 0):02d}"
    )


if shows and movies and INTRO_EPISODE and os.path.exists(INTRO_EPISODE):
    # S02E04 (S02E05 suit : l'encart du générique a un épisode à proposer)
    rpc("Player.Open", {"item": {"episodeid": BYK[(2, 4)]}, "options": {"resume": False}})
    opened = wait_skip(15.0)  # « Previously on » dès le début (après la sortie son)
    wait(0.8)
    log(f"passer : bouton {'« ' + xbmc.getInfoLabel('Control.GetLabel(301)') + ' »' if opened else 'ABSENT'} sur {chapter_now()}")
    shot("21a-passer-recap")
    press("Select")
    wait(2.0)
    log(f"après « Passer le récap » : {chapter_now()}")
    opened = wait_skip(6.0)  # chapitre « Opening »
    wait(0.8)
    log(f"passer : bouton {'« ' + xbmc.getInfoLabel('Control.GetLabel(301)') + ' »' if opened else 'ABSENT'} sur {chapter_now()}")
    shot("21b-passer-intro")
    press("Select")
    wait(2.0)
    log(f"après « Passer l'intro » : {chapter_now()}")
    # Sous-titres FR automatiques : audio anglais, aucun sous-titre → Bazarr (faux)
    folder = os.path.dirname(INTRO_EPISODE)
    with open(os.path.join(folder, "Severance - S02E04.fr.srt"), "w", encoding="utf-8") as srt:
        srt.write("1\n00:00:00,000 --> 00:03:00,000\nSous-titres français automatiques (banc)\n")
    for _ in range(30):
        wait(0.5)
        if "S02E04.fr.srt" in json.dumps(rpc(
            "Player.GetProperties", {"playerid": 1, "properties": ["currentsubtitle", "subtitles"]}
        )):  # fmt: skip
            break
    current = rpc("Player.GetProperties", {"playerid": 1, "properties": ["currentsubtitle", "subtitleenabled"]})
    log(
        "sous-titres automatiques : "
        f"{(current.get('currentsubtitle') or {}).get('language', '?')} "
        f"({'affichés' if current.get('subtitleenabled') else 'masqués'})"
    )
    shot("21c-sous-titres-auto")
    # Générique de fin : l'encart « Épisode suivant » sans attendre les 20 dernières secondes
    seek(72)
    opened = wait_upnext(8.0)
    wait(1.0)
    log(f"générique de fin : encart {'ouvert' if opened else 'ABSENT'} sur {chapter_now()}")
    shot("21d-generique-encart")
    press("Back")
    xbmc.executebuiltin("PlayerControl(Stop)")
    wait(2.0)
    xbmc.executebuiltin("ActivateWindow(Home)")
    wait(2.0)
else:
    log("épisode aux chapitres nommés absent : section 1.17 sautée")


# ── 7. Réouverture (cache), panne serveur ──────────────────────────────────
run_plugin("home")
wait(1.2)
shot("08-reouverture-cache")

# ── 8. Lecture d'une vidéo + écran Salon par-dessus ────────────────────────
if DEMO_VIDEO and os.path.exists(DEMO_VIDEO):
    press("Back")
    wait(1.5)
    # Présentée comme un épisode identifié (comme depuis la médiathèque Kodi) :
    # le suivi de lecture doit envoyer série, épisode et affiche (1.10).
    episode = xbmcgui.ListItem("Cold Harbor", path=DEMO_VIDEO)
    tag = episode.getVideoInfoTag()
    tag.setMediaType("episode")
    tag.setTitle("Cold Harbor")
    tag.setTvShowTitle("Severance")
    tag.setSeason(2)
    tag.setEpisode(10)
    tag.setYear(2022)
    episode.setArt(
        {"tvshow.poster": f"{MOCK}/img/poster-1.jpg", "fanart": f"{MOCK}/img/fanart-1.jpg"}
    )
    xbmc.Player().play(DEMO_VIDEO, episode)
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
    # Caméra Eufy : « Personne détectée » pendant le film → pop-up avec la photo
    CAMERA = (
        f"{MOCK}/__emit?type=camera&camera=Entr%C3%A9e&label=Personne%20d%C3%A9tect%C3%A9e"
        "&detection=person&snapshot_id=1&at=2026-10-11T19:42:05%2B00:00"
    )
    urllib.request.urlopen(CAMERA).read()
    for _ in range(30):
        wait(0.5)
        if xbmc.getInfoLabel("Window(Home).Property(arrmada.camera_popup)") == "1":
            break
    wait(1.5)
    log(
        "pop-up caméra : "
        + ("ouverte" if xbmc.getInfoLabel("Window(Home).Property(arrmada.camera_popup)") else "ABSENTE")
        + f", film {'en lecture' if xbmc.Player().isPlayingVideo() else 'ARRÊTÉ'}"
    )
    shot("09d-camera-popup")
    # 1.14.1 : la pop-up se ferme seule après 5 s
    for _ in range(14):
        wait(0.5)
        if not xbmc.getInfoLabel("Window(Home).Property(arrmada.camera_popup)"):
            break
    log(
        "pop-up caméra après 5 s : "
        + ("ENCORE LÀ" if xbmc.getInfoLabel("Window(Home).Property(arrmada.camera_popup)") else "fermée seule")
    )
    # Nouvelle détection : cette fois une touche la ferme tout de suite
    urllib.request.urlopen(CAMERA).read()
    for _ in range(30):
        wait(0.5)
        if xbmc.getInfoLabel("Window(Home).Property(arrmada.camera_popup)") == "1":
            break
    wait(1.0)
    press("Select")  # toute touche ferme la pop-up, le film continue
    wait(1.0)
    log(
        "après une touche : pop-up "
        + ("ENCORE LÀ" if xbmc.getInfoLabel("Window(Home).Property(arrmada.camera_popup)") else "fermée")
        + f", film {'en lecture' if xbmc.Player().isPlayingVideo() else 'ARRÊTÉ'}"
    )
    xbmc.executebuiltin("PlayerControl(Stop)")
    wait(1.0)
    sent = json.loads(urllib.request.urlopen(f"{MOCK}/__scrobbles").read())
    log("suivi de lecture : " + " → ".join(
        f"{s.get('event')}({s.get('title')} S{s.get('season')}E{s.get('episode')}"
        f" pause={s.get('paused')} affiche={'oui' if s.get('poster') else 'non'})"
        for s in sent
    ))
    # … mais un résumé « Pendant ta séance » apparaît à l'arrêt
    for _ in range(16):
        wait(0.5)
        if xbmc.getCondVisibility("Window.IsVisible(notification)"):
            break
    wait(0.8)
    shot("09c-resume-seance")
    wait(6.0)  # la bulle du résumé s'efface
    # Hors lecture : une simple bulle, avec la photo en vignette
    urllib.request.urlopen(CAMERA.replace("snapshot_id=1", "snapshot_id=2")).read()
    for _ in range(16):
        wait(0.5)
        if xbmc.getCondVisibility("Window.IsVisible(notification)"):
            break
    wait(0.8)
    log(f"caméra hors lecture : bulle {xbmc.getCondVisibility('Window.IsVisible(notification)')}")
    shot("09e-camera-bulle")
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
