"""Applis & sources : add-ons, TV en direct, dossiers, favoris (lib/apps_data.py)."""

from __future__ import annotations

from datetime import datetime

import apps_data as ad


def test_tabs_depend_on_the_device():
    keys = [key for key, _ in ad.visible_tabs(has_pvr=False, is_android=False)]
    assert keys == ["video", "music", "folders", "favourites"]
    keys = [key for key, _ in ad.visible_tabs(has_pvr=True, is_android=True)]
    assert keys == ["video", "live", "music", "folders", "favourites", "android"]
    assert ad.tab_index(ad.TABS, "folders") == 3
    assert ad.tab_index(ad.TABS, "inconnu") == 0
    # Tuiles à la racine des onglets ; liste pour les chaînes et dans un dossier
    assert ad.layout_for("video", browsing=False) == "tiles"
    assert ad.layout_for("live", browsing=False) == "list"
    assert ad.layout_for("video", browsing=True) == "list"


def test_clean_strips_kodi_formatting():
    assert ad.clean("[B][COLOR red]YouTube[/COLOR][/B]") == "YouTube"
    assert ad.clean("Ligne 1[CR]Ligne 2") == "Ligne 1 Ligne 2"
    assert ad.first_line("x" * 200, limit=10) == "xxxxxxxxx…"


def test_addons_are_sorted_and_arrmada_is_hidden():
    addons = [
        {
            "addonid": "plugin.video.youtube",
            "name": "YouTube",
            "type": "xbmc.python.pluginsource",
            "thumbnail": "yt.png",
            "summary": "Regarder YouTube\nsuite",
        },
        {"addonid": "script.arrmada", "name": "ArrMada", "type": "xbmc.python.pluginsource"},
        {"addonid": "plugin.video.arte", "name": "[B]arte[/B]", "type": "xbmc.python.pluginsource"},
        {"addonid": "script.tool", "name": "Outil", "type": "xbmc.python.script"},
        {"addonid": "plugin.video.off", "name": "Désactivé", "enabled": False},
    ]
    apps = ad.addon_entries(addons)
    assert [app["label"] for app in apps] == ["arte", "Outil", "YouTube"]
    youtube = apps[2]
    assert youtube["target"] == "browse" and youtube["path"] == "plugin://plugin.video.youtube/"
    assert youtube["label2"] == "Regarder YouTube" and youtube["art"]["thumb"] == "yt.png"
    tool = apps[1]
    assert tool["target"] == "run" and tool["command"] == "RunAddon(script.tool)"
    assert apps[0]["art"]["thumb"] == ad.ADDON_ICON  # pas d'icône : celle du skin
    assert ad.known_addons(apps) == {
        "plugin.video.arte": "video",
        "plugin.video.youtube": "video",
    }


def test_sources_and_android_apps():
    sources = ad.source_entries(
        [
            {"file": "smb://nas/videos/", "label": "Vidéos perso"},
            {"file": "nfs://nas/concerts/", "label": "Concerts"},
            {"file": "addons://sources/video/", "label": "Add-ons"},  # pas un dossier
        ]
    )
    assert [(s["label"], s["label2"]) for s in sources] == [
        ("Vidéos perso", "Partage réseau (SMB)"),
        ("Concerts", "Partage réseau (NFS)"),
    ]
    assert sources[0]["target"] == "browse" and sources[0]["art"]["thumb"] == ad.FOLDER_ICON
    apps = ad.android_entries(
        [
            {"file": "androidapp://sources/apps/com.netflix.ninja", "label": "Netflix"},
            {"file": 'androidapp://sources/apps/bad"pkg', "label": "Piège"},
            {"file": "androidapp://sources/apps/com.disney.disneyplus", "label": "Disney+"},
        ]
    )
    assert [app["label"] for app in apps] == ["Disney+", "Netflix"]
    assert apps[1]["command"] == 'StartAndroidActivity("com.netflix.ninja")'


def test_directory_keeps_order_and_shows_resume():
    files = [
        {"file": "plugin://x/?page=2", "filetype": "directory", "label": "Page suivante"},
        {
            "file": "smb://nas/a.mkv",
            "filetype": "file",
            "label": "Concert",
            "runtime": 5400,
            "resume": {"position": 1800, "total": 5400},
            "art": {"thumb": "t", "fanart": "f"},
        },
        {
            "file": "smb://nas/b.mkv",
            "filetype": "file",
            "label": "",
            "playcount": 2,
            "season": 1,
            "episode": 3,
            "runtime": 1500,
        },
        {"file": "", "filetype": "file", "label": "sans chemin"},
    ]
    apps = ad.directory_entries(files, "video", parent="smb://nas/")
    assert [app["label"] for app in apps] == ["Page suivante", "Concert", "b.mkv"]
    folder, concert, episode = apps
    assert folder["target"] == "browse" and folder["label2"] == ""
    assert concert["target"] == "play" and concert["resume"] == 1800
    assert concert["label2"] == "1 h 30 · Reprendre à 30:00"
    assert concert["bar"] == "bar-034" and concert["parent"] == "smb://nas/"
    assert episode["label2"] == "S01E03 · 25 min · Vu" and episode["watched"]
    # Kodi met -1 hors épisode : pas de « S-1E-1 »
    plain = ad.directory_entries(
        [{"file": "p", "filetype": "file", "label": "x", "season": -1, "episode": -1}]
    )[0]
    assert plain["label2"] == ""
    assert episode["art"]["thumb"] == ad.FILE_ICON
    assert ad.breadcrumb(["YouTube", "Abonnements"]) == "YouTube › Abonnements"
    assert ad.breadcrumb(["a", "b", "c", "d"]) == "… › b › c › d"
    assert (ad.count_label(0), ad.count_label(1), ad.count_label(3)) == (
        "",
        "1 élément",
        "3 éléments",
    )


def test_channels_show_current_programme_in_local_time():
    now = datetime(2026, 10, 11, 20, 40)
    channels = [
        {
            "channelid": 3,
            "label": "France 2",
            "channelnumber": 2,
            "thumbnail": "f2.png",
            "broadcastnow": {
                "title": "Journal",
                "runtime": 40,
                "progress": 600,
                "plotoutline": "L'actualité.",
            },
            "broadcastnext": {"title": "Film du soir"},
        },
        {"channelid": 4, "label": "Cachée", "hidden": True},
        {"channelid": 5, "label": "Sans guide"},
    ]
    apps = ad.channel_entries(channels, now)
    assert [app["label"] for app in apps] == ["France 2", "Sans guide"]
    f2, bare = apps
    # 40 min dont 10 passées : fin dans 30 min → 21:10
    assert f2["label2"] == "Journal · jusqu'à 21:10"
    assert f2["plot"] == "L'actualité.[CR]Ensuite, à 21:10 : Film du soir"
    assert f2["bar"] == "bar-024" and f2["number"] == "2" and f2["id"] == "3"
    assert bare["label2"] == "Pas de programme" and bare["art"]["thumb"] == ad.LIVE_ICON


FAVOURITES_XML = """<favourites>
    <favourite name="YouTube" thumb="yt.png">RunAddon(plugin.video.youtube)</favourite>
    <favourite name="Concerts" thumb="c.png">ActivateWindow(10025,&quot;smb://nas/concerts,live/&quot;,return)</favourite>
    <favourite name="Netflix">StartAndroidActivity(&quot;com.netflix.ninja&quot;)</favourite>
    <favourite name="ArrMada · Accueil">PlayMedia(&quot;plugin://script.arrmada/?action=shell&quot;)</favourite>
    <favourite name="Réglages">ActivateWindow(Settings)</favourite>
</favourites>"""


def test_favourites_open_in_arrmada_when_possible():
    favourites = ad.parse_favourites(FAVOURITES_XML)
    assert len(favourites) == 5 and favourites[0]["thumb"] == "yt.png"
    apps = ad.favourite_entries(favourites, {"plugin.video.youtube": "video"})
    assert [app["label"] for app in apps] == ["YouTube", "Concerts", "Netflix", "Réglages"]
    youtube, concerts, netflix, settings = apps
    assert (youtube["target"], youtube["path"]) == ("browse", "plugin://plugin.video.youtube/")
    # La virgule entre guillemets fait partie du chemin
    assert (concerts["target"], concerts["path"]) == ("browse", "smb://nas/concerts,live/")
    assert netflix["target"] == "run"
    assert netflix["command"] == 'StartAndroidActivity("com.netflix.ninja")'
    assert settings["command"] == "ActivateWindow(Settings)"
    assert ad.parse_favourites("<pas du xml") == []


def test_split_command_handles_quotes_and_escapes():
    assert ad.split_command('ActivateWindow(10025,"a,b",return)') == (
        "ActivateWindow",
        ["10025", "a,b", "return"],
    )
    assert ad.split_command('PlayMedia("x\\"y")') == ("PlayMedia", ['x"y'])
    assert ad.split_command("Quit") == ("Quit", [])
    assert ad.quote('a"b') == '"a\\"b"'
    assert (
        ad.kodi_window_command("smb://nas/", "video")
        == 'ActivateWindow(Videos,"smb://nas/",return)'
    )
    assert ad.kodi_window_command("plugin://m/", "music").startswith("ActivateWindow(Music,")


def test_home_row_puts_favourites_first_without_duplicates():
    addons = ad.addon_entries(
        [{"addonid": "plugin.video.youtube", "name": "YouTube", "type": "xbmc.python.pluginsource"}]
    )
    favourites = ad.favourite_entries(ad.parse_favourites(FAVOURITES_XML), ad.known_addons(addons))
    row = ad.home_apps(favourites, ad.live_tile("pvr.png"), addons)
    labels = [app["label"] for app in row]
    # YouTube en favori et en add-on : une seule tuile
    assert labels == ["YouTube", "Concerts", "Netflix", "Réglages", "TV en direct"]
    assert row[4]["target"] == "tab" and row[4]["art"]["thumb"] == "pvr.png"
    assert len(ad.home_apps([], None, addons * 50, limit=5)) == 1  # dédoublonné


def test_shell_entry_round_trip():
    app = ad.addon_entries(
        [
            {
                "addonid": "plugin.video.youtube",
                "name": "YouTube",
                "type": "xbmc.python.pluginsource",
                "thumbnail": "yt.png",
                "fanart": "fa.jpg",
                "description": "Vidéos.",
            }
        ]
    )[0]
    entry = ad.shell_entry(app)
    assert entry["action"]["action"] == "app" and entry["art"]["fanart"] == "fa.jpg"
    assert entry["info"]["plot"] == "Vidéos." and entry["context"] == []
    assert entry["props"]["icon_only"] == "1"  # l'en-tête n'agrandit pas l'icône
    assert all(isinstance(value, str) for value in entry["action"].values())  # URL plugin://
    back = ad.app_from_action(entry["action"])
    assert (back["target"], back["path"], back["media"]) == (
        "browse",
        "plugin://plugin.video.youtube/",
        "video",
    )


def test_long_press_always_offers_kodi_as_a_way_out():
    folder = ad.directory_entries(
        [{"file": "smb://nas/a/", "filetype": "directory", "label": "A"}], parent="smb://nas/"
    )[0]
    assert [op for op, _ in ad.context_ops(folder)] == ["open_kodi"]
    assert ad.op_command("open_kodi", folder) == 'ActivateWindow(Videos,"smb://nas/a/",return)'
    started = ad.directory_entries(
        [
            {
                "file": "smb://nas/b.mkv",
                "filetype": "file",
                "label": "B",
                "runtime": 600,
                "resume": {"position": 120, "total": 600},
            }
        ],
        parent="smb://nas/",
    )[0]
    assert [op for op, _ in ad.context_ops(started)] == ["from_start", "open_kodi"]
    assert ad.op_command("open_kodi", started) == 'ActivateWindow(Videos,"smb://nas/",return)'
    addon = ad.addon_entries(
        [{"addonid": "plugin.video.youtube", "name": "YouTube", "type": "xbmc.python.pluginsource"}]
    )[0]
    assert [op for op, _ in ad.context_ops(addon)] == ["open_kodi", "addon_settings"]
    assert ad.op_command("addon_settings", addon) == "Addon.OpenSettings(plugin.video.youtube)"
    channel = ad.channel_entries([{"channelid": 1, "label": "TF1"}], datetime(2026, 1, 1))[0]
    assert [op for op, _ in ad.context_ops(channel)] == ["tv_guide"]
