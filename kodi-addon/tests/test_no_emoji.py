"""Aucun emoji dans les textes de l'appli : la police de la TV n'en a pas.

Constaté sur la TV : « 📥 Téléchargement terminé » s'affichait avec un carré
vide devant, et les menus « Options avancées » (✅, ➕, 🎯…) pareil. On lit
les chaînes de caractères du code Python (pas les commentaires) ; les flèches
« → » des docstrings et du journal restent permises, seuls les emojis et
pictogrammes sont refusés.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

import toast_data

ADDON = Path(__file__).resolve().parent.parent / "script.arrmada"
# Ceux de toast_data.SYMBOLS, sans les flèches (permises hors affichage)
EMOJI = re.compile(toast_data.SYMBOLS.pattern.replace(chr(0x2190) + "-" + chr(0x21FF), ""))
SOURCES = sorted(p for p in ADDON.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ADDON)))
def test_no_emoji_in_strings(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    offenders = [
        f"ligne {tok.start[0]} : {tok.string[:60]}"
        for tok in tokenize.generate_tokens(io.StringIO(text).readline)
        if tok.type == tokenize.STRING and EMOJI.search(tok.string)
    ]
    assert not offenders, f"emoji non affichable sur la TV : {offenders}"
