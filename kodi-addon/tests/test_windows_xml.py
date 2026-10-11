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
