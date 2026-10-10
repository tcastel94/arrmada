"""Cohérence de l'écran « Accueil » : XML ↔ Python ↔ textures ↔ polices SiLVO.

Kodi n'affiche aucune erreur visible quand un identifiant, une texture ou une
police n'existe pas : le contrôle reste vide, ou la police retombe sur font13.
Ces tests attrapent ces fautes de frappe avant qu'elles n'arrivent sur la TV.
"""

from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import make_textures

ADDON = Path(__file__).resolve().parent.parent / "script.arrmada"
XML = ADDON / "resources" / "skins" / "Default" / "1080i" / "script-arrmada-home.xml"
MEDIA = ADDON / "resources" / "skins" / "Default" / "media"
WINDOW_PY = ADDON / "lib" / "home_window.py"

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


@pytest.fixture(scope="module")
def tree() -> ET.Element:
    return ET.parse(XML).getroot()  # échoue si le XML est mal formé


def _window_constants() -> dict[str, object]:
    """Constantes d'identifiants de home_window.py, lues sans importer Kodi."""
    module = ast.parse(WINDOW_PY.read_text(encoding="utf-8"))
    out: dict[str, object] = {}
    for node in module.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", "")
            if name.isupper():
                try:
                    out[name] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return out


def test_python_ids_exist_in_xml(tree: ET.Element) -> None:
    xml_ids = {int(c.get("id")) for c in tree.iter("control") if c.get("id")}
    consts = _window_constants()
    expected: set[int] = set()
    for name in (
        "RAIL",
        "SERVICES",
        "BUTTONS",
        "BTN_SEARCH",
        "BTN_REFRESH",
        "BTN_DIAG",
        "DIAG_CLOSE",
        "STORAGE_PROGRESS",
    ):
        expected.add(int(consts[name]))
    expected.update(int(i) for i in consts["DL_PROGRESS"])
    assert expected <= xml_ids, f"IDs absents du XML : {sorted(expected - xml_ids)}"


def test_ids_are_unique(tree: ET.Element) -> None:
    ids = [c.get("id") for c in tree.iter("control") if c.get("id")]
    assert len(ids) == len(set(ids)), "identifiant de contrôle en double"


def test_fonts_exist_in_silvo(tree: ET.Element) -> None:
    used = {f.text.strip() for f in tree.iter("font")}
    assert used, "aucune police trouvée : le test ne lit pas le bon fichier ?"
    assert used <= SILVO_FONTS, f"polices absentes de SiLVO : {sorted(used - SILVO_FONTS)}"


def test_textures_exist_and_are_used() -> None:
    xml = XML.read_text(encoding="utf-8")
    referenced = set(re.findall(r"arrmada/[\w.-]+\.png", xml))
    on_disk = {f"arrmada/{p.name}" for p in (MEDIA / "arrmada").glob("*.png")}
    assert referenced <= on_disk, f"textures manquantes : {sorted(referenced - on_disk)}"
    assert on_disk <= referenced, f"textures inutilisées : {sorted(on_disk - referenced)}"


def test_committed_textures_match_generator(tmp_path: Path) -> None:
    """Les PNG du dépôt sont bien ceux que produit tools/make_textures.py."""
    make_textures.main(tmp_path)
    for generated in tmp_path.glob("*.png"):
        committed = MEDIA / "arrmada" / generated.name
        assert committed.read_bytes() == generated.read_bytes(), (
            f"{generated.name} n'est pas à jour : relance python3 kodi-addon/tools/make_textures.py"
        )


def test_no_glyph_missing_from_silvo_font(tree: ET.Element) -> None:
    """Roboto Condensed (police de SiLVO) n'a pas ces symboles : carré vide à l'écran.

    Constaté sur le banc de test (panneau Diagnostic). Seul le texte affiché
    compte (pas les commentaires du XML), et la ligne « Glyphes » du
    diagnostic a le droit de les afficher, justement pour le vérifier.
    """
    missing = {"→", "★", "✓", "✔", "▶", "⏸", "●"}
    labels = [lbl.text or "" for lbl in tree.iter("label") if "Glyphes" not in (lbl.text or "")]
    offenders = [text for text in labels if any(ch in text for ch in missing)]
    assert not offenders, f"glyphes non affichables : {offenders}"
