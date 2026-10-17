#!/usr/bin/env python3
"""Pose la bulle ArrMada (appli 1.24.1) dans chaque écran plein écran.

Pourquoi un script : Kodi ne partage pas de morceau de mise en page entre les
fenêtres d'une extension. Le même bloc doit donc figurer dans les 9 écrans
(liste : lib/toast_data.py, WINDOWS). Ce script le place (ou le remet à jour)
entre deux repères, juste avant la fin de chaque écran, pour qu'il soit
dessiné par-dessus tout le reste ; c'est l'équivalent d'un bloc géré par
Ansible (blockinfile).

Les écrans générés (accueil, Téléchargements) l'ajoutent eux-mêmes via apply().

Usage : python3 kodi-addon/tools/toast_xml.py
Un test vérifie que chaque écran porte le bloc à jour.
"""

# ruff: noqa: E501 — gabarits XML de Kodi, lignes longues assumées
from __future__ import annotations

import sys
from pathlib import Path

ADDON = Path(__file__).resolve().parent.parent / "script.arrmada"
SKIN = ADDON / "resources" / "skins" / "Default" / "1080i"
sys.path.insert(0, str(ADDON / "lib"))

import toast_data  # noqa: E402 — chemin ajouté juste au-dessus

BEGIN = "\t\t<!-- toast:begin"
END = "\t\t<!-- toast:end -->\n"
TAIL = "\t</controls>\n</window>\n"

# Bas droite, 644 × 124 : au-dessus de tout, sans prendre le focus (une
# image et deux textes, aucun bouton : la télécommande reste à l'écran).
BLOCK = (
    """		<!-- toast:begin · bulle ArrMada, bloc posé par tools/toast_xml.py (ne pas modifier ici) -->
		<control type="group">
			<left>1236</left><top>912</top>
			<visible>!String.IsEmpty(Window(Home).Property(arrmada.toast))</visible>
			<animation effect="slide" start="0,48" end="0,0" time="320" tween="cubic" easing="out">Visible</animation>
			<animation effect="fade" start="0" end="100" time="320">Visible</animation>
			<animation effect="fade" start="100" end="0" time="240">Hidden</animation>
			<control type="image">
				<left>-20</left><top>-20</top><width>684</width><height>164</height>
				<texture border="56" colordiffuse="664A9EFF">arrmada/glow.png</texture>
			</control>
			<control type="image">
				<width>644</width><height>124</height>
				<texture border="26" colordiffuse="F7121826">arrmada/rounded-24.png</texture>
			</control>
			<control type="image">
				<width>644</width><height>124</height>
				<texture border="26" colordiffuse="804A9EFF">arrmada/ring-24.png</texture>
				<visible>String.IsEmpty(Window(Home).Property(arrmada.toast.error))</visible>
			</control>
			<control type="image">
				<width>644</width><height>124</height>
				<texture border="26" colordiffuse="99F87171">arrmada/ring-24.png</texture>
				<visible>!String.IsEmpty(Window(Home).Property(arrmada.toast.error))</visible>
			</control>
			<control type="image">
				<left>18</left><top>14</top><width>64</width><height>96</height>
				<aspectratio>keep</aspectratio>
				<texture background="true">$INFO[Window(Home).Property(arrmada.toast.icon)]</texture>
			</control>
			<control type="label">
				<left>100</left><top>14</top><width>524</width><height>36</height>
				<font>font13</font>
				<textcolor>FF8CC4FF</textcolor>
				<aligny>center</aligny>
				<label>$INFO[Window(Home).Property(arrmada.toast.heading)]</label>
				<visible>String.IsEmpty(Window(Home).Property(arrmada.toast.error))</visible>
			</control>
			<control type="label">
				<left>100</left><top>14</top><width>524</width><height>36</height>
				<font>font13</font>
				<textcolor>FFFCA5A5</textcolor>
				<aligny>center</aligny>
				<label>$INFO[Window(Home).Property(arrmada.toast.heading)]</label>
				<visible>!String.IsEmpty(Window(Home).Property(arrmada.toast.error))</visible>
			</control>
			<control type="textbox">
				<left>100</left><top>52</top><width>524</width><height>62</height>
				<font>font12</font>
				<textcolor>D9F5F7FA</textcolor>
				<label>$INFO[Window(Home).Property(arrmada.toast.message)]</label>
			</control>
		</control>
"""
    + END
)


def apply(text: str) -> str:
    """Le XML d'un écran avec le bloc à jour (ajouté avant la fin, ou remplacé)."""
    start = text.find(BEGIN)
    if start != -1:
        stop = text.index(END, start) + len(END)
        return text[:start] + BLOCK + text[stop:]
    if not text.endswith(TAIL):
        raise ValueError("fin d'écran inattendue : « </controls></window> » introuvable")
    return text[: -len(TAIL)] + BLOCK + TAIL


# Écrans dont le XML est produit par un générateur (qui appelle apply lui-même)
GENERATED = {"script-arrmada-shell.xml", "script-arrmada-downloads.xml"}


def main() -> None:
    for name in toast_data.WINDOWS:
        if name in GENERATED:
            continue
        path = SKIN / name
        before = path.read_text(encoding="utf-8")
        after = apply(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
            print(f"OK : {name}")


if __name__ == "__main__":
    main()
