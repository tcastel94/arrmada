#!/usr/bin/env python3
"""Génère la mise en page de l'accueil média ArrMada (ADR-004, phase 4.2).

Pourquoi un script plutôt qu'un XML écrit à la main ?
  Les 4 rangées de l'accueil (Reprendre, Ajouts récents, Pour toi, Bientôt)
  et les 9 boutons du menu partagent la même mise en page, à quelques
  valeurs près. Les écrire 4 fois, c'est 4 endroits à corriger à chaque
  retouche. Le script les écrit à partir d'un seul modèle, comme un gabarit
  Jinja ou Ansible produit des fichiers de configuration.

Usage : python3 kodi-addon/tools/make_shell_xml.py
Le fichier produit est versionné ; un test vérifie qu'il est à jour.
"""

# ruff: noqa: E501 — gabarits XML de Kodi, lignes longues assumées
from __future__ import annotations

import sys
from pathlib import Path

OUT = (
    Path(__file__).resolve().parent.parent
    / "script.arrmada"
    / "resources"
    / "skins"
    / "Default"
    / "1080i"
    / "script-arrmada-shell.xml"
)

# (groupe, liste, titre, forme des vignettes) : ordre de shell_data.ROWS
ROWS = (
    (601, 610, "Reprendre", "landscape"),
    (602, 620, "Ajouts récents", "poster"),
    (603, 630, "Pour toi", "poster"),
    (604, 640, "Bientôt", "poster"),
)
# Libellés du menu : ordre de shell_data.MENU (boutons 401 à 409)
MENU = (
    "Accueil",
    "Films",
    "Séries",
    "Découvrir",
    "Rechercher",
    "Téléchargements",
    "Salon",
    "Tableau de bord",
    "Réglages",
)


def menu_button(index: int, label: str) -> str:
    return f"""			<control type="button" id="{401 + index}">
				<width>auto</width><height>56</height>
				<label>{label}</label>
				<font>font13</font>
				<textoffsetx>22</textoffsetx>
				<textcolor>CCF5F7FA</textcolor>
				<focusedcolor>FF0A0E16</focusedcolor>
				<aligny>center</aligny>
				<texturenofocus border="14" colordiffuse="00FFFFFF">arrmada/rounded-12.png</texturenofocus>
				<texturefocus border="14" colordiffuse="FF4A9EFF">arrmada/rounded-12.png</texturefocus>
				<animation effect="zoom" start="100" end="106" time="160" tween="cubic" easing="out" center="auto">Focus</animation>
				<animation effect="zoom" start="106" end="100" time="160" tween="cubic" easing="out" center="auto">UnFocus</animation>
			</control>"""


def watched_pill(left: int, top: int, focused: bool) -> str:
    color = "FF34D399" if focused else "E634D399"
    return f"""					<control type="group">
						<left>{left}</left><top>{top}</top>
						<visible>String.IsEqual(ListItem.Property(watched),1)</visible>
						<control type="image">
							<left>0</left><top>0</top><width>62</width><height>30</height>
							<texture border="14" colordiffuse="{color}">arrmada/rounded-12.png</texture>
						</control>
						<control type="label">
							<left>0</left><top>0</top><width>62</width><height>30</height>
							<font>font10</font>
							<textcolor>FF0A0E16</textcolor>
							<align>center</align><aligny>center</aligny>
							<label>Vu</label>
						</control>
					</control>"""


def landscape(list_id: int, focused: bool) -> str:
    """Vignette 16:9 (Reprendre) : image, barre de reprise, titre, état."""
    zoom = (
        f"""					<animation type="Focus">
						<effect type="zoom" start="100" end="106" time="220" tween="cubic" easing="out" center="194,117"/>
					</animation>
					<animation type="UnFocus">
						<effect type="zoom" start="106" end="100" time="180" tween="cubic" easing="out" center="194,117"/>
					</animation>
					<control type="image">
						<left>-30</left><top>-30</top><width>448</width><height>278</height>
						<texture border="56" colordiffuse="A64A9EFF">arrmada/glow.png</texture>
						<visible>Control.HasFocus({list_id})</visible>
					</control>
"""
        if focused
        else ""
    )
    ring = (
        f"""					<control type="image">
						<left>-4</left><top>-4</top><width>396</width><height>226</height>
						<texture border="26" colordiffuse="FF4A9EFF">arrmada/poster-ring.png</texture>
						<visible>Control.HasFocus({list_id})</visible>
					</control>
"""
        if focused
        else ""
    )
    label_color = "FFF5F7FA" if focused else "B3F5F7FA"
    return f"""				<control type="group">
					<left>16</left><top>10</top>
{zoom}					<control type="image">
						<left>0</left><top>0</top><width>388</width><height>218</height>
						<texture border="26" colordiffuse="FF1A2233">arrmada/rounded-24.png</texture>
					</control>
					<control type="image">
						<left>0</left><top>0</top><width>388</width><height>218</height>
						<aspectratio>scale</aspectratio>
						<fadetime>200</fadetime>
						<texture background="true">$INFO[ListItem.Art(thumb)]</texture>
					</control>
					<control type="image">
						<left>0</left><top>138</top><width>388</width><height>80</height>
						<texture colordiffuse="CC0A0E16">arrmada/grad-v.png</texture>
					</control>
{ring}					<control type="image">
						<left>16</left><top>198</top><width>356</width><height>8</height>
						<texture>arrmada/progress/$INFO[ListItem.Property(bar)].png</texture>
						<visible>!String.IsEmpty(ListItem.Property(bar))</visible>
					</control>
				</control>
				<control type="label">
					<left>22</left><top>236</top><width>376</width><height>28</height>
					<font>font12</font>
					<textcolor>{label_color}</textcolor>
					<aligny>center</aligny>
					<label>$INFO[ListItem.Label]</label>
				</control>
				<control type="label">
					<left>22</left><top>262</top><width>376</width><height>24</height>
					<font>font10</font>
					<textcolor>FF9CCBFF</textcolor>
					<aligny>center</aligny>
					<label>$INFO[ListItem.Property(status)]</label>
				</control>"""


def poster(list_id: int, focused: bool) -> str:
    """Affiche 2:3 (Ajouts récents, Pour toi, Bientôt) : pastille « Vu », barre."""
    zoom = (
        f"""					<animation type="Focus">
						<effect type="zoom" start="100" end="108" time="220" tween="cubic" easing="out" center="102,153"/>
					</animation>
					<animation type="UnFocus">
						<effect type="zoom" start="108" end="100" time="180" tween="cubic" easing="out" center="102,153"/>
					</animation>
					<control type="image">
						<left>-34</left><top>-34</top><width>272</width><height>374</height>
						<texture border="56" colordiffuse="A64A9EFF">arrmada/glow.png</texture>
						<visible>Control.HasFocus({list_id})</visible>
					</control>
"""
        if focused
        else ""
    )
    ring = (
        f"""					<control type="image">
						<left>0</left><top>0</top><width>204</width><height>306</height>
						<texture colordiffuse="FF4A9EFF">arrmada/poster-ring.png</texture>
						<visible>Control.HasFocus({list_id})</visible>
					</control>
"""
        if focused
        else ""
    )
    label_color = "FFF5F7FA" if focused else "B3F5F7FA"
    return f"""				<control type="group">
					<left>16</left><top>16</top>
{zoom}					<control type="image">
						<left>0</left><top>0</top><width>204</width><height>306</height>
						<texture border="26" colordiffuse="FF1A2233">arrmada/rounded-24.png</texture>
					</control>
					<control type="label">
						<left>12</left><top>0</top><width>180</width><height>306</height>
						<font>font12</font>
						<textcolor>B3F5F7FA</textcolor>
						<align>center</align><aligny>center</aligny>
						<wrapmultiline>true</wrapmultiline>
						<label>$INFO[ListItem.Label]</label>
						<visible>String.IsEmpty(ListItem.Art(poster))</visible>
					</control>
					<control type="image">
						<left>0</left><top>0</top><width>204</width><height>306</height>
						<aspectratio>scale</aspectratio>
						<fadetime>200</fadetime>
						<texture background="true" diffuse="arrmada/poster-mask.png">$INFO[ListItem.Art(poster)]</texture>
					</control>
{ring}{watched_pill(132, 12, focused)}
					<control type="image">
						<left>14</left><top>284</top><width>176</width><height>8</height>
						<texture>arrmada/progress/$INFO[ListItem.Property(bar)].png</texture>
						<visible>!String.IsEmpty(ListItem.Property(bar))</visible>
					</control>
				</control>
				<control type="label">
					<left>16</left><top>334</top><width>204</width><height>30</height>
					<font>font10</font>
					<textcolor>{label_color}</textcolor>
					<align>center</align><aligny>center</aligny>
					<label>$INFO[ListItem.Label]</label>
				</control>"""


def row(group_id: int, list_id: int, title: str, shape: str, up: int, down: int) -> str:
    """Une rangée : titre + liste horizontale, masquée si elle est vide.

    Haut / Bas sont déclarés rangée par rangée (`up`, `down`) : la liste
    verticale (500) ne les transmet pas aux listes imbriquées (constaté sur le
    banc). Une rangée vide est masquée donc non focalisable : Kodi suit alors
    SA navigation dans la même direction et passe à la suivante.
    """
    if shape == "landscape":
        height, item_w, item_h, layout = 300, 420, 290, landscape
    else:
        height, item_w, item_h, layout = 380, 236, 376, poster
    down_tag = f"<ondown>{down}</ondown>" if down else ""
    return f"""			<!-- Rangée « {title} » -->
			<control type="group" id="{group_id}">
				<width>1840</width><height>{height + 52}</height>
				<defaultcontrol>{list_id}</defaultcontrol>
				<visible>Integer.IsGreater(Container({list_id}).NumItems,0)</visible>
				<control type="image">
					<left>16</left><top>14</top><width>6</width><height>26</height>
					<texture colordiffuse="FF4A9EFF">arrmada/white.png</texture>
				</control>
				<control type="label">
					<left>36</left><top>6</top><width>900</width><height>42</height>
					<font>font13_title</font>
					<textcolor>FFF5F7FA</textcolor>
					<aligny>center</aligny>
					<label>{title}</label>
				</control>
				<control type="list" id="{list_id}">
					<left>0</left><top>48</top><width>1840</width><height>{height}</height>
					<orientation>horizontal</orientation>
					<onup>{up}</onup>{down_tag}
					<scrolltime tween="cubic" easing="out">280</scrolltime>
					<itemlayout width="{item_w}" height="{item_h}">
{layout(list_id, False)}
					</itemlayout>
					<focusedlayout width="{item_w}" height="{item_h}">
{layout(list_id, True)}
					</focusedlayout>
				</control>
			</control>"""


HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<!--
  ArrMada — accueil média, la « coquille » qui remplace l'accueil de Kodi
  (ADR-004, phase 4.2).

  FICHIER GÉNÉRÉ par kodi-addon/tools/make_shell_xml.py : modifier le script,
  pas ce fichier (un test vérifie qu'ils correspondent).

  Repère 1920 × 1080. Données posées par lib/shell_window.py :
    - menu principal (400, boutons 401 à 409, ordre de shell_data.MENU) ;
    - en-tête de l'élément sélectionné (propriétés hero_*) ;
    - rangées (500) : Reprendre (610), Ajouts récents (620), Pour toi (630),
      Bientôt (640). Une rangée vide disparaît.
  Navigation : menu (400) ↓ rangées (500) ; Retour : menu « Quitter ? ».
-->"""

BODY = """<window>
	<defaultcontrol always="false">500</defaultcontrol>
	<backgroundcolor>FF0A0E16</backgroundcolor>
	<animation effect="fade" start="0" end="100" time="400" tween="sine" easing="out">WindowOpen</animation>
	<animation effect="fade" start="100" end="0" time="200">WindowClose</animation>
	<controls>

		<!-- ═══════════════ FOND : fanart de l'élément sélectionné ═══════════════ -->
		<control type="image">
			<left>0</left><top>0</top><width>1920</width><height>1080</height>
			<texture colordiffuse="FF0A0E16">arrmada/white.png</texture>
		</control>
		<control type="image">
			<left>0</left><top>0</top><width>1920</width><height>1080</height>
			<aspectratio>scale</aspectratio>
			<fadetime>700</fadetime>
			<texture background="true" colordiffuse="99FFFFFF">$INFO[Window.Property(hero_fanart)]</texture>
			<animation effect="zoom" start="100" end="108" time="26000" tween="sine" easing="inout" pulse="true" condition="true" center="960,540">Conditional</animation>
		</control>
		<control type="image">
			<left>0</left><top>0</top><width>1500</width><height>1080</height>
			<texture colordiffuse="FF0A0E16">arrmada/grad-h.png</texture>
		</control>
		<control type="image">
			<left>0</left><top>380</top><width>1920</width><height>700</height>
			<texture colordiffuse="FF0A0E16">arrmada/grad-v.png</texture>
		</control>
		<control type="image">
			<left>-300</left><top>-380</top><width>1200</width><height>900</height>
			<texture colordiffuse="334A9EFF">arrmada/blob.png</texture>
			<animation effect="fade" start="100" end="50" time="5000" tween="sine" pulse="true" condition="true">Conditional</animation>
		</control>

		<!-- ═══════════════ MENU PRINCIPAL + HEURE ═══════════════ -->
		<control type="grouplist" id="400">
			<left>80</left><top>28</top><width>1560</width><height>56</height>
			<orientation>horizontal</orientation>
			<itemgap>6</itemgap>
			<ondown>500</ondown>
			<animation effect="slide" start="0,-40" end="0,0" time="500" tween="cubic" easing="out">WindowOpen</animation>
@MENU@
		</control>
		<control type="label">
			<left>1640</left><top>28</top><width>200</width><height>56</height>
			<font>font30</font>
			<textcolor>E6F5F7FA</textcolor>
			<align>right</align><aligny>center</aligny>
			<label>$INFO[System.Time]</label>
		</control>

		<!-- ═══════════════ EN-TÊTE : élément sélectionné ═══════════════ -->
		<control type="group">
			<animation effect="fade" start="0" end="100" time="500" delay="150">WindowOpen</animation>
			<control type="image">
				<left>96</left><top>112</top><width>760</width><height>170</height>
				<aspectratio align="left" aligny="bottom">keep</aspectratio>
				<fadetime>300</fadetime>
				<texture background="true">$INFO[Window.Property(hero_clearlogo)]</texture>
				<visible>!String.IsEmpty(Window.Property(hero_clearlogo))</visible>
			</control>
			<control type="textbox">
				<left>96</left><top>130</top><width>1300</width><height>150</height>
				<font>font52_bold</font>
				<textcolor>FFF5F7FA</textcolor>
				<aligny>bottom</aligny>
				<label>$INFO[Window.Property(hero_title)]</label>
				<visible>String.IsEmpty(Window.Property(hero_clearlogo))</visible>
			</control>
			<control type="label">
				<left>96</left><top>292</top><width>1300</width><height>36</height>
				<font>font13</font>
				<textcolor>FF9CCBFF</textcolor>
				<aligny>center</aligny>
				<label>$INFO[Window.Property(hero_status)]</label>
			</control>
			<control type="label">
				<left>96</left><top>330</top><width>1300</width><height>34</height>
				<font>font12</font>
				<textcolor>D9DCE3EE</textcolor>
				<aligny>center</aligny>
				<label>$INFO[Window.Property(hero_meta)]</label>
			</control>
			<control type="textbox">
				<left>96</left><top>372</top><width>1050</width><height>120</height>
				<font>font12</font>
				<textcolor>D9E6E8EE</textcolor>
				<label>$INFO[Window.Property(hero_plot)]</label>
			</control>
		</control>

		<!-- Rien à afficher (premier démarrage sans serveur ni médiathèque) -->
		<control type="label">
			<left>96</left><top>600</top><width>1600</width><height>60</height>
			<font>font13</font>
			<textcolor>80C9D3E0</textcolor>
			<aligny>center</aligny>
			<label>Rien à afficher pour l'instant : le menu du haut mène aux films, aux séries et au tableau de bord.</label>
			<visible>!String.IsEmpty(Window.Property(empty))</visible>
		</control>

		<!-- ═══════════════ RANGÉES ═══════════════ -->
		<control type="grouplist" id="500">
			<left>80</left><top>500</top><width>1840</width><height>580</height>
			<orientation>vertical</orientation>
			<itemgap>4</itemgap>
			<onup>400</onup>
			<scrolltime tween="cubic" easing="out">300</scrolltime>
			<animation effect="slide" start="0,80" end="0,0" time="600" delay="200" tween="cubic" easing="out">WindowOpen</animation>
@ROWS@
		</control>
	</controls>
</window>
"""


def render() -> str:
    body = BODY.replace("@MENU@", "\n".join(menu_button(i, label) for i, label in enumerate(MENU)))
    lists = [list_id for _, list_id, _, _ in ROWS]
    rows = []
    for index, (group_id, list_id, title, shape) in enumerate(ROWS):
        up = lists[index - 1] if index else 400  # 1re rangée : le menu
        down = lists[index + 1] if index + 1 < len(lists) else 0
        rows.append(row(group_id, list_id, title, shape, up, down))
    body = body.replace("@ROWS@", "\n".join(rows))
    return f"{HEADER}\n{body}"


def main(out: Path = OUT) -> None:
    out.write_text(render(), encoding="utf-8")
    print(f"OK : {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
