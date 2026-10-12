"""Cohérence des écrans sur mesure : XML ↔ Python ↔ textures ↔ polices SiLVO.

Kodi n'affiche aucune erreur visible quand un identifiant, une texture ou une
police n'existe pas : le contrôle reste vide, ou la police retombe sur font13.
Ces tests attrapent ces fautes de frappe avant qu'elles n'arrivent sur la TV,
pour les écrans sur mesure (Accueil, Fiche média, Téléchargements, Salon,
Appairage).
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import make_shell_xml
import make_textures

ADDON = Path(__file__).resolve().parent.parent / "script.arrmada"
SKIN = ADDON / "resources" / "skins" / "Default"
MEDIA = SKIN / "media"

# Écran → (fichier XML, module Python qui le remplit)
WINDOWS = {
    "home": ("script-arrmada-home.xml", "home_window.py"),
    "detail": ("script-arrmada-detail.xml", "detail_window.py"),
    "downloads": ("script-arrmada-downloads.xml", "downloads_window.py"),
    "salon": ("script-arrmada-salon.xml", "salon_window.py"),
    "pair": ("script-arrmada-pair.xml", "pair_window.py"),
    "qr": ("script-arrmada-qr.xml", "qr_window.py"),
    "series": ("script-arrmada-series.xml", "series_window.py"),
    "grid": ("script-arrmada-grid.xml", "grid_window.py"),
    "shell": ("script-arrmada-shell.xml", "shell_window.py"),
    "apps": ("script-arrmada-apps.xml", "apps_window.py"),
    "camera": ("script-arrmada-camera.xml", "camera_window.py"),
    "upnext": ("script-arrmada-upnext.xml", "upnext_window.py"),
    "player": ("script-arrmada-player.xml", "player_window.py"),
    "skip": ("script-arrmada-skip.xml", "skip_window.py"),
}

# Noms de police présents dans TOUS les jeux de polices (« fontsets ») d'Aeon
# Nox SiLVO 10.0.4 (branche omega, 16x9/Font.xml) : l'écran reste juste quel
# que soit le jeu de polices choisi dans les réglages du skin.
SILVO_FONTS = {
    "BigAssFont",
    "WeatherTemp",
    "font10",
    "font11",
    "font12",
    "font12_title",
    "font13",
    "font13_title",
    "font13b",
    "font14",
    "font14_textbox",
    "font14_textbox2",
    "font14_title",
    "font15",
    "font15_bold",
    "font15_textbox",
    "font15_title",
    "font16",
    "font16_textbox",
    "font16_title",
    "font16_title_bold",
    "font16bold_textbox",
    "font24_bold",
    "font24_title",
    "font28_bold",
    "font30",
    "font30_title",
    "font30_title_bold",
    "font35_title",
    "font45caps_title",
    "font48",
    "font48_bold",
    "font48_title",
    "font52_bold",
    "font65",
    "fontArial15",
    "fontCDalbum",
    "fontCDartist",
    "font_MainMenu",
    "font_VerticalMainMenu",
    "font_musicviz",
    "font_version",
}


def _xml_path(window: str) -> Path:
    return SKIN / "1080i" / WINDOWS[window][0]


def _tree(window: str) -> ET.Element:
    return ET.parse(_xml_path(window)).getroot()  # échoue si le XML est mal formé


def _control_ids_from_python(window: str) -> set[int]:
    """Identifiants de contrôles déclarés dans le module Python, lus sans Kodi.

    Convention : toute constante en MAJUSCULES valant un entier ≥ 100 (ou un
    tuple de tels entiers) est un identifiant de contrôle du XML. Les autres
    constantes (délais, pas de volume…) restent sous 100.
    """
    source = (ADDON / "lib" / WINDOWS[window][1]).read_text(encoding="utf-8")
    ids: set[int] = set()
    for node in ast.parse(source).body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        name = getattr(node.targets[0], "id", "")
        if not name.isupper():
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            continue
        values = value if isinstance(value, tuple) else (value,)
        if values and all(
            isinstance(v, int) and not isinstance(v, bool) and v >= 100 for v in values
        ):
            ids.update(values)
    return ids


@pytest.mark.parametrize("window", WINDOWS)
def test_python_ids_exist_in_xml(window: str) -> None:
    xml_ids = {int(c.get("id")) for c in _tree(window).iter("control") if c.get("id")}
    expected = _control_ids_from_python(window)
    assert expected, "aucun identifiant trouvé : convention non respectée ?"
    assert expected <= xml_ids, (
        f"IDs absents de {WINDOWS[window][0]} : {sorted(expected - xml_ids)}"
    )


@pytest.mark.parametrize("window", WINDOWS)
def test_ids_are_unique(window: str) -> None:
    ids = [c.get("id") for c in _tree(window).iter("control") if c.get("id")]
    assert len(ids) == len(set(ids)), "identifiant de contrôle en double"


@pytest.mark.parametrize("window", WINDOWS)
def test_fonts_exist_in_silvo(window: str) -> None:
    used = {f.text.strip() for f in _tree(window).iter("font")}
    assert used, "aucune police trouvée : le test ne lit pas le bon fichier ?"
    assert used <= SILVO_FONTS, f"polices absentes de SiLVO : {sorted(used - SILVO_FONTS)}"


@pytest.mark.parametrize("window", WINDOWS)
def test_no_glyph_missing_from_silvo_font(window: str) -> None:
    """Roboto Condensed (police de SiLVO) n'a pas ces symboles : carré vide à l'écran.

    Constaté sur le banc de test (panneau Diagnostic). Seul le texte affiché
    compte (pas les commentaires du XML), et la ligne « Glyphes » du
    diagnostic a le droit de les afficher, justement pour le vérifier.
    """
    missing = {"→", "★", "✓", "✔", "▶", "⏸", "●"}
    labels = [
        lbl.text or "" for lbl in _tree(window).iter("label") if "Glyphes" not in (lbl.text or "")
    ]
    offenders = [text for text in labels if any(ch in text for ch in missing)]
    assert not offenders, f"glyphes non affichables : {offenders}"


@pytest.mark.parametrize("window", WINDOWS)
def test_only_the_focused_control_is_solid_accent(window: str) -> None:
    """À la télécommande, le seul repère est « ce qui est bleu plein ».

    Un bouton non focalisé peut être teinté d'accent (bouton principal), mais
    jamais opaque : sinon on ne sait plus où est le focus (constaté sur le
    banc : « Lire » et « Bande-annonce » bleus en même temps).
    """
    offenders = []
    for texture in _tree(window).iter("texturenofocus"):
        color = (texture.get("colordiffuse") or "").upper()
        if len(color) == 8 and color.endswith("4A9EFF") and int(color[:2], 16) >= 0x80:
            offenders.append(color)
    assert not offenders, f"bouton non focalisé en bleu plein : {offenders}"


@pytest.mark.parametrize("window", WINDOWS)
def test_no_numeric_label(window: str) -> None:
    """Un `<label>` purement numérique est lu par Kodi comme un identifiant de
    texte traduit (« 1 » → « Images »…), pas comme le chiffre : écrire
    `$NUMBER[1]`. Constaté sur le banc (numéros d'étape de l'appairage)."""
    numeric = [
        lbl.text for lbl in _tree(window).iter("label") if (lbl.text or "").strip().isdigit()
    ]
    assert not numeric, f"libellés numériques (utiliser $NUMBER[...]) : {numeric}"


def test_textures_exist_and_are_used() -> None:
    xml = "".join(_xml_path(w).read_text(encoding="utf-8") for w in WINDOWS)
    referenced = set(re.findall(r"arrmada/[\w.-]+\.png", xml))
    on_disk = {f"arrmada/{p.name}" for p in (MEDIA / "arrmada").glob("*.png")}
    assert referenced <= on_disk, f"textures manquantes : {sorted(referenced - on_disk)}"
    assert on_disk <= referenced, f"textures inutilisées : {sorted(on_disk - referenced)}"


def test_progress_bars_cover_every_step() -> None:
    """Les barres des listes (bar-000 … bar-100, pas de 2 %) existent toutes."""
    xml = "".join(_xml_path(w).read_text(encoding="utf-8") for w in WINDOWS)
    assert "arrmada/progress/$INFO[" in xml
    bars = {p.name for p in (MEDIA / "arrmada" / "progress").glob("*.png")}
    assert bars == {f"bar-{pct:03d}.png" for pct in range(0, 101, 2)}


def test_committed_textures_match_generator(tmp_path: Path) -> None:
    """Les PNG du dépôt sont bien ceux que produit tools/make_textures.py."""
    make_textures.main(tmp_path)
    for generated in tmp_path.rglob("*.png"):
        committed = MEDIA / "arrmada" / generated.relative_to(tmp_path)
        assert committed.read_bytes() == generated.read_bytes(), (
            f"{generated.name} n'est pas à jour : relance python3 kodi-addon/tools/make_textures.py"
        )


def test_shell_xml_matches_generator() -> None:
    """L'accueil média est généré (tools/make_shell_xml.py) : le fichier versionné est à jour."""
    assert _xml_path("shell").read_text(encoding="utf-8") == make_shell_xml.render(), (
        "script-arrmada-shell.xml pas à jour : python3 kodi-addon/tools/make_shell_xml.py"
    )


def test_shell_menu_and_rows_follow_shell_data() -> None:
    """Boutons et rangées dans le même ordre que shell_data (le Python s'y fie)."""
    import shell_data

    # shell_window importe xbmc : ses constantes sont lues sans l'exécuter
    source = (ADDON / "lib" / "shell_window.py").read_text(encoding="utf-8")
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and getattr(node.targets[0], "id", "") in ("MENU_BUTTONS", "ROW_LISTS")
    }
    assert len(constants["MENU_BUTTONS"]) == len(shell_data.MENU) == len(make_shell_xml.MENU)
    assert [label for _, label in shell_data.MENU] == list(make_shell_xml.MENU)
    assert [title for _, _, title, _ in make_shell_xml.ROWS] == [t for _, t in shell_data.ROWS]
    assert [list_id for _, list_id, _, _ in make_shell_xml.ROWS] == list(constants["ROW_LISTS"])


def test_detail_disc_comes_out_and_goes_back_in() -> None:
    """Fiche (1.20.0) : le disque sort du boîtier, tourne, rentre à la fermeture.

    - dessiné AVANT le boîtier (Kodi dessine dans l'ordre : il est derrière) ;
    - sortie (Conditional sur disc_out) et rentrée (WindowClose) de même
      distance : à la fermeture il finit exactement dans le boîtier ;
    - les deux visuels du disque tournent, le reflet non (la lampe est fixe).
    """
    root = ET.parse(_xml_path("detail")).getroot()
    groups = [
        g
        for g in root.iter("control")
        if g.get("type") == "group"
        and "disc_out" in "".join(a.get("condition", "") for a in g.findall("animation"))
    ]
    assert len(groups) == 1, "un seul groupe « disque » piloté par disc_out"
    disc = groups[0]
    slides = {a.text: a for a in disc.findall("animation") if a.get("effect") == "slide"}
    out_x = int(slides["Conditional"].get("end").split(",")[0])
    back_x = int(slides["WindowClose"].get("end").split(",")[0])
    assert out_x < 0 and out_x + back_x == 0

    images = [c for c in disc.iter("control") if c.get("type") == "image"]
    spinning = [
        c for c in images if any(a.get("effect") == "rotate" for a in c.findall("animation"))
    ]
    textures = [c.findtext("texture") or "" for c in spinning]
    assert any("Window.Property(discart)" in t for t in textures), "rond imprimé fanart.tv"
    assert any("Window.Property(poster)" in t for t in textures), "disque dessiné avec l'affiche"
    shine = [c for c in images if "disc-shine" in (c.findtext("texture") or "")]
    assert shine and not shine[0].findall("animation"), "le reflet ne tourne pas"

    # Le disque est déclaré avant les boîtiers → caché derrière eux
    xml = _xml_path("detail").read_text(encoding="utf-8")
    assert xml.index("disc-shadow.png") < min(
        xml.index(f"case-{name}.png") for name in make_textures.CASES
    )
    for case in ("uhd", "bluray", "dvd"):
        assert f"String.IsEqual(Window.Property(case_format),{case})" in xml


def _rect(control: ET.Element) -> tuple[int, int, int, int]:
    return tuple(int(control.findtext(k) or 0) for k in ("left", "top", "width", "height"))  # type: ignore[return-value]


def test_detail_cases_fit_their_textures() -> None:
    """Chaque boîtier (case-*.png) est posé à sa taille réelle, PAR-DESSUS
    l'affiche, et l'affiche occupe exactement la jaquette prévue par le
    générateur (sinon elle déborde du plastique ou laisse un trou)."""
    root = ET.parse(_xml_path("detail")).getroot()
    groups = {
        name: group
        for group in root.iter("control")
        if group.get("type") == "group"
        for name in make_textures.CASES
        if any(
            (c.findtext("texture") or "") == f"arrmada/case-{name}.png"
            for c in group.findall("control")
        )
    }
    assert set(groups) == set(make_textures.CASES), "un boîtier par format"
    for name, group in groups.items():
        children = group.findall("control")
        overlay = next(
            c for c in children if (c.findtext("texture") or "") == f"arrmada/case-{name}.png"
        )
        height = make_textures.CASES[name][0]
        assert _rect(overlay) == (0, 0, make_textures.CASE_W, height), name
        poster = next(
            c for c in children if "Window.Property(poster)" in (c.findtext("texture") or "")
        )
        assert _rect(poster) == make_textures.case_window(name), name
        assert children.index(poster) < children.index(overlay), f"{name} : boîtier sur l'affiche"
        assert poster.findtext("aspectratio") == "scale", f"{name} : affiche recadrée, pas déformée"
