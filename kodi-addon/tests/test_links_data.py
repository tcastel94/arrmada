"""Liens TV → web app (phase 3) : chemins, fichiers QR, ouverture sur Android."""

from __future__ import annotations

import links_data


def test_media_paths_match_the_web_app_routes() -> None:
    assert links_data.media_path("movie", 12) == "/media/movie/12"
    assert links_data.media_path("tvshow", "7") == "/media/series/7"
    assert links_data.media_path("episode", 7) == "/media/series/7"
    assert links_data.media_path("movie", None) == ""
    assert links_data.media_path("movie", "abc") == ""


def test_pages_are_web_app_paths() -> None:
    for page in links_data.PAGES.values():
        assert page.path.startswith("/") and "//" not in page.path
        assert page.title and page.text
    # Textes affichés tels quels : pas de glyphe absent de la police SiLVO
    missing = {"→", "★", "✓", "✔", "▶", "⏸", "●"}
    for page in links_data.PAGES.values():
        assert not missing & set(page.title + page.text)


def test_qr_file_name_changes_with_the_url() -> None:
    first = links_data.qr_file_name("http://nas:3420/media/movie/1")
    assert first == links_data.qr_file_name("http://nas:3420/media/movie/1")
    assert first != links_data.qr_file_name("http://nas:3420/media/movie/2")
    assert first.startswith("arrmada-qr-") and first.endswith(".png")


def test_android_browser_command() -> None:
    assert links_data.android_open_url("http://nas:3420/dashboard") == (
        'StartAndroidActivity("","android.intent.action.VIEW","","http://nas:3420/dashboard")'
    )
    # Rien qui puisse casser la commande Kodi, ni autre chose qu'une adresse web
    assert links_data.android_open_url('http://x/"),Quit()') is None
    assert links_data.android_open_url("file:///sdcard/x") is None
    assert links_data.android_open_url("http://x/a b") is None


def test_shortcuts_skip_existing_favourites() -> None:
    """Kodi « ajoute ou enlève » : un raccourci déjà présent ne doit pas être renvoyé."""
    favourites = [
        {
            "title": "ArrMada · Accueil",
            "type": "media",
            "path": "plugin://script.arrmada/?action=home",
        },
        {"title": "Films", "type": "window", "window": "videos", "windowparameter": "videodb://"},
    ]
    missing = links_data.missing_shortcuts(favourites)
    assert [action for _, action in missing] == ["queue", "salon", "search_input"]
    assert len(links_data.missing_shortcuts(None)) == len(links_data.SHORTCUTS)
    assert (
        links_data.missing_shortcuts(
            [{"path": links_data.shortcut_path(action)} for _, action in links_data.SHORTCUTS]
        )
        == []
    )


def test_every_shortcut_opens_a_window() -> None:
    """Un favori lance l'action comme une lecture : l'add-on doit la reconnaître."""
    for _, action in links_data.SHORTCUTS:
        assert action in links_data.WINDOW_ACTIONS
