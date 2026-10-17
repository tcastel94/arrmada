#!/usr/bin/env python3
"""Génère la mise en page de l'écran Téléchargements (ADR-005, lot 3).

Pourquoi un script : chaque carte « Pour ce soir » a 5 étapes (Trouvé,
Téléchargement, Import, Sous-titres, Prêt) en 4 états chacune, et chaque ligne de la file
6 couleurs d'état, le tout deux fois (élément normal et élément sélectionné).
Écrit à la main, c'est une centaine de blocs presque identiques ; ici, un
seul modèle (comme un gabarit Jinja ou Ansible).

Usage : python3 kodi-addon/tools/make_downloads_xml.py
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
    / "script-arrmada-downloads.xml"
)

# Famille d'état d'une ligne : (nom, couleur du trait, couleur de la pastille)
FAMILIES = [
    ("active", "FF4A9EFF", "334A9EFF"),
    ("paused", "FFFBBF24", "33FBBF24"),
    ("queued", "80C9D3E0", "1FFFFFFF"),
    ("import", "FF34D399", "3334D399"),
    ("error", "FFF87171", "40F87171"),
    ("done", "FF34D399", "3334D399"),
]
# Étape d'une carte : (état, fond de la pastille) ; "" = étape pas encore atteinte
STEP_COLORS = [
    ("done", "3334D399"),
    ("now", "554A9EFF"),
    ("err", "40F87171"),
    ("", "14FFFFFF"),
]


def steps(t):
    out = []
    for n in range(1, 6):
        left = 224 + (n - 1) * 124
        for state, bg in STEP_COLORS:
            cond = (
                f"String.IsEqual(ListItem.Property(s{n}_state),{state})"
                if state
                else f"String.IsEmpty(ListItem.Property(s{n}_state))"
            )
            out.append(f"""{t}<control type="image">
{t}	<left>{left}</left><top>206</top><width>116</width><height>36</height>
{t}	<texture border="14" colordiffuse="{bg}">arrmada/rounded-12.png</texture>
{t}	<visible>{cond}</visible>
{t}</control>""")
        out.append(f"""{t}<control type="label">
{t}	<left>{left}</left><top>206</top><width>116</width><height>36</height>
{t}	<font>font10</font>
{t}	<textcolor>FFF5F7FA</textcolor>
{t}	<align>center</align><aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(s{n})]</label>
{t}</control>""")
    return "\n".join(out)


def card(t, focused):
    out = []
    if focused:
        out.append(f"""{t}<control type="image">
{t}	<left>-12</left><top>-14</top><width>884</width><height>312</height>
{t}	<texture border="56" colordiffuse="664A9EFF">arrmada/glow.png</texture>
{t}	<visible>Control.HasFocus(720)</visible>
{t}</control>
{t}<control type="image">
{t}	<width>860</width><height>284</height>
{t}	<texture border="26" colordiffuse="FF16203A">arrmada/rounded-24.png</texture>
{t}	<visible>Control.HasFocus(720)</visible>
{t}</control>
{t}<control type="image">
{t}	<width>860</width><height>284</height>
{t}	<texture border="26" colordiffuse="FF4A9EFF">arrmada/ring-24.png</texture>
{t}	<visible>Control.HasFocus(720)</visible>
{t}</control>
{t}<control type="image">
{t}	<width>860</width><height>284</height>
{t}	<texture border="26" colordiffuse="FF121826">arrmada/rounded-24.png</texture>
{t}	<visible>!Control.HasFocus(720)</visible>
{t}</control>""")
    else:
        out.append(f"""{t}<control type="image">
{t}	<width>860</width><height>284</height>
{t}	<texture border="26" colordiffuse="FF121826">arrmada/rounded-24.png</texture>
{t}</control>""")
    out.append(f"""{t}<control type="image">
{t}	<width>860</width><height>284</height>
{t}	<texture border="26" colordiffuse="3334D399">arrmada/ring-24.png</texture>
{t}	<visible>String.IsEqual(ListItem.Property(phase),ready){" + !Control.HasFocus(720)" if focused else ""}</visible>
{t}</control>
{t}<control type="image">
{t}	<left>20</left><top>20</top><width>176</width><height>244</height>
{t}	<texture border="14" colordiffuse="1AFFFFFF">arrmada/rounded-12.png</texture>
{t}</control>
{t}<control type="image">
{t}	<left>20</left><top>20</top><width>176</width><height>244</height>
{t}	<aspectratio>scale</aspectratio>
{t}	<texture background="true">$INFO[ListItem.Property(poster)]</texture>
{t}</control>
{t}<control type="label">
{t}	<left>224</left><top>16</top><width>612</width><height>44</height>
{t}	<font>font13</font>
{t}	<textcolor>FFF5F7FA</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Label]</label>
{t}</control>
{t}<control type="label">
{t}	<left>224</left><top>58</top><width>612</width><height>30</height>
{t}	<font>font10</font>
{t}	<textcolor>99C9D3E0</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(who)]</label>
{t}</control>
{t}<control type="label">
{t}	<left>224</left><top>92</top><width>612</width><height>60</height>
{t}	<font>font30</font>
{t}	<textcolor>FFF5F7FA</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(headline)]</label>
{t}	<visible>!String.IsEqual(ListItem.Property(phase),blocked) + !String.IsEqual(ListItem.Property(phase),ready)</visible>
{t}</control>
{t}<control type="label">
{t}	<left>224</left><top>92</top><width>612</width><height>60</height>
{t}	<font>font30</font>
{t}	<textcolor>FF6EE7B7</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(headline)]</label>
{t}	<visible>String.IsEqual(ListItem.Property(phase),ready)</visible>
{t}</control>
{t}<control type="label">
{t}	<left>224</left><top>92</top><width>612</width><height>60</height>
{t}	<font>font30</font>
{t}	<textcolor>FFFCA5A5</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(headline)]</label>
{t}	<visible>String.IsEqual(ListItem.Property(phase),blocked)</visible>
{t}</control>
{t}<control type="image">
{t}	<left>224</left><top>156</top><width>600</width><height>12</height>
{t}	<texture>arrmada/progress/$INFO[ListItem.Property(bar)].png</texture>
{t}</control>
{t}<control type="label">
{t}	<left>224</left><top>170</top><width>612</width><height>30</height>
{t}	<font>font10</font>
{t}	<textcolor>B3DCE3EE</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(detail)]</label>
{t}</control>""")
    out.append(steps(t))
    if focused:
        out.append(f"""{t}<control type="label">
{t}	<left>224</left><top>248</top><width>612</width><height>28</height>
{t}	<font>font10</font>
{t}	<textcolor>FF8CC4FF</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(hint)]</label>
{t}	<visible>Control.HasFocus(720)</visible>
{t}</control>""")
    return "\n".join(out)


def row(t, focused):
    out = []
    if focused:
        out.append(f"""{t}<control type="image">
{t}	<left>-12</left><top>-20</top><width>1784</width><height>148</height>
{t}	<texture border="56" colordiffuse="664A9EFF">arrmada/glow.png</texture>
{t}	<visible>Control.HasFocus(700)</visible>
{t}</control>
{t}<control type="image">
{t}	<left>16</left><top>6</top><width>1728</width><height>98</height>
{t}	<texture border="26" colordiffuse="FF16203A">arrmada/rounded-24.png</texture>
{t}	<visible>Control.HasFocus(700)</visible>
{t}</control>
{t}<control type="image">
{t}	<left>16</left><top>6</top><width>1728</width><height>98</height>
{t}	<texture border="26" colordiffuse="FF4A9EFF">arrmada/ring-24.png</texture>
{t}	<visible>Control.HasFocus(700)</visible>
{t}</control>
{t}<control type="image">
{t}	<left>16</left><top>6</top><width>1728</width><height>98</height>
{t}	<texture border="26" colordiffuse="14FFFFFF">arrmada/rounded-24.png</texture>
{t}	<visible>!Control.HasFocus(700)</visible>
{t}</control>""")
    else:
        out.append(f"""{t}<control type="image">
{t}	<left>16</left><top>6</top><width>1728</width><height>98</height>
{t}	<texture border="26" colordiffuse="14FFFFFF">arrmada/rounded-24.png</texture>
{t}</control>""")
    for fam, stripe, _pill in FAMILIES:
        out.append(f"""{t}<control type="image">
{t}	<left>38</left><top>26</top><width>6</width><height>58</height>
{t}	<texture border="3" colordiffuse="{stripe}">arrmada/rounded-12.png</texture>
{t}	<visible>String.IsEqual(ListItem.Property(family),{fam})</visible>
{t}</control>""")
    out.append(f"""{t}<control type="image">
{t}	<left>62</left><top>14</top><width>56</width><height>82</height>
{t}	<aspectratio>scale</aspectratio>
{t}	<texture background="true">$INFO[ListItem.Property(poster)]</texture>
{t}</control>
{t}<control type="label">
{t}	<left>138</left><top>12</top><width>940</width><height>38</height>
{t}	<font>font13</font>
{t}	<textcolor>FFF5F7FA</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Label]</label>
{t}</control>
{t}<control type="label">
{t}	<left>138</left><top>48</top><width>940</width><height>28</height>
{t}	<font>font10</font>
{t}	<textcolor>99C9D3E0</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(meta)]</label>
{t}	<visible>!String.IsEqual(ListItem.Property(family),error)</visible>
{t}</control>
{t}<control type="label">
{t}	<left>138</left><top>48</top><width>940</width><height>28</height>
{t}	<font>font10</font>
{t}	<textcolor>FFFCA5A5</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(detail)]</label>
{t}	<visible>String.IsEqual(ListItem.Property(family),error)</visible>
{t}</control>
{t}<control type="image">
{t}	<left>138</left><top>82</top><width>930</width><height>10</height>
{t}	<texture>arrmada/progress/$INFO[ListItem.Property(bar)].png</texture>
{t}</control>
{t}<control type="label">
{t}	<left>1100</left><top>8</top><width>240</width><height>56</height>
{t}	<font>font30</font>
{t}	<textcolor>FFF5F7FA</textcolor>
{t}	<align>right</align><aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(pct)]</label>
{t}</control>
{t}<control type="label">
{t}	<left>1060</left><top>66</top><width>280</width><height>28</height>
{t}	<font>font10</font>
{t}	<textcolor>99C9D3E0</textcolor>
{t}	<align>right</align><aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(eta_speed)]</label>
{t}</control>""")
    for fam, _stripe, pill in FAMILIES:
        out.append(f"""{t}<control type="image">
{t}	<left>1388</left><top>18</top><width>220</width><height>36</height>
{t}	<texture border="14" colordiffuse="{pill}">arrmada/rounded-12.png</texture>
{t}	<visible>String.IsEqual(ListItem.Property(family),{fam})</visible>
{t}</control>""")
    out.append(f"""{t}<control type="label">
{t}	<left>1388</left><top>18</top><width>220</width><height>36</height>
{t}	<font>font10</font>
{t}	<textcolor>FFF5F7FA</textcolor>
{t}	<align>center</align><aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(status)]</label>
{t}</control>""")
    if focused:
        out.append(f"""{t}<control type="label">
{t}	<left>1388</left><top>62</top><width>340</width><height>28</height>
{t}	<font>font10</font>
{t}	<textcolor>FF8CC4FF</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(hint)]</label>
{t}	<visible>Control.HasFocus(700)</visible>
{t}</control>
{t}<control type="label">
{t}	<left>1388</left><top>62</top><width>340</width><height>28</height>
{t}	<font>font10</font>
{t}	<textcolor>99C9D3E0</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(sizes)]</label>
{t}	<visible>!Control.HasFocus(700)</visible>
{t}</control>""")
    else:
        out.append(f"""{t}<control type="label">
{t}	<left>1388</left><top>62</top><width>340</width><height>28</height>
{t}	<font>font10</font>
{t}	<textcolor>99C9D3E0</textcolor>
{t}	<aligny>center</aligny>
{t}	<label>$INFO[ListItem.Property(sizes)]</label>
{t}</control>""")
    return "\n".join(out)


def button(t, cid, label, width):
    return f"""{t}<control type="button" id="{cid}">
{t}	<width>{width}</width><height>56</height>
{t}	<label>{label}</label>
{t}	<font>font12</font>
{t}	<textcolor>D9F5F7FA</textcolor>
{t}	<focusedcolor>FF0A0E16</focusedcolor>
{t}	<align>center</align><aligny>center</aligny>
{t}	<texturenofocus border="14" colordiffuse="1AFFFFFF">arrmada/rounded-12.png</texturenofocus>
{t}	<texturefocus border="14" colordiffuse="FF4A9EFF">arrmada/rounded-12.png</texturefocus>
{t}	<animation effect="zoom" start="100" end="106" time="160" tween="cubic" easing="out" center="auto">Focus</animation>
{t}	<animation effect="zoom" start="106" end="100" time="160" tween="cubic" easing="out" center="auto">UnFocus</animation>
{t}</control>"""


T4, T5 = "\t" * 4, "\t" * 5


def render() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!--
  ArrMada — écran « Téléchargements » (ADR-005, lot 3 ; phase 2 de l'ADR-003).

  Rempli par lib/downloads_window.py (logique : lib/board_data.py et
  screens_data.build_downloads), depuis GET /api/kodi/downloads/board,
  rafraîchi toutes les 5 s, mis à jour sur place.

    720  « Pour ce soir » : une carte par demande lancée depuis une TV (heure
         « Prêt vers », étapes Trouvé → Téléchargement → Import → Sous-titres → Prêt)
    700  le reste de la file (Radarr + Sonarr)
    710  711 « Pause sauf ce soir » (les demandes TV sont en priorité Force :
         SABnzbd les télécharge même en pause), 712 « Tout reprendre »
  OK sur une carte ou une ligne : menu d'actions (Passer en tête, Pause,
  Débloquer, Fiche, Annuler ma demande, Relancer la recherche).
  Barres : images pré-rendues arrmada/progress/bar-XXX.png.
  Généré par kodi-addon/tools/make_downloads_xml.py : modifier le script,
  pas ce fichier (un test vérifie qu'il est à jour).
-->
<window>
	<defaultcontrol always="false">720</defaultcontrol>
	<backgroundcolor>FF0A0E16</backgroundcolor>
	<animation effect="fade" start="0" end="100" time="300" tween="sine" easing="out">WindowOpen</animation>
	<animation effect="fade" start="100" end="0" time="200">WindowClose</animation>
	<controls>
		<control type="image">
			<left>0</left><top>0</top><width>1920</width><height>1080</height>
			<texture colordiffuse="FF0A0E16">arrmada/white.png</texture>
		</control>
		<control type="image">
			<left>0</left><top>0</top><width>1920</width><height>1080</height>
			<aspectratio>scale</aspectratio>
			<fadetime>600</fadetime>
			<texture background="true" colordiffuse="33FFFFFF">$INFO[Container(720).ListItem.Property(fanart)]</texture>
		</control>
		<control type="image">
			<left>0</left><top>0</top><width>1920</width><height>1080</height>
			<texture flipy="true" colordiffuse="E60A0E16">arrmada/grad-v.png</texture>
		</control>
		<control type="image">
			<left>900</left><top>-480</top><width>1400</width><height>1000</height>
			<texture colordiffuse="404A9EFF">arrmada/blob.png</texture>
			<animation effect="fade" start="100" end="45" time="5000" tween="sine" pulse="true" condition="true">Conditional</animation>
		</control>
		<control type="image">
			<left>-420</left><top>640</top><width>1200</width><height>820</height>
			<texture colordiffuse="2222E0EE">arrmada/blob.png</texture>
		</control>

		<!-- En-tête -->
		<control type="group">
			<animation effect="slide" start="0,-40" end="0,0" time="450" tween="cubic" easing="out">WindowOpen</animation>
			<control type="label">
				<left>96</left><top>40</top><width>1000</width><height>76</height>
				<font>font48_bold</font>
				<textcolor>FFF5F7FA</textcolor>
				<aligny>center</aligny>
				<label>Téléchargements</label>
			</control>
			<control type="label">
				<left>96</left><top>112</top><width>1000</width><height>40</height>
				<font>font13</font>
				<textcolor>B3DCE3EE</textcolor>
				<aligny>center</aligny>
				<label>$INFO[Window.Property(summary)]</label>
			</control>
			<control type="image">
				<left>1080</left><top>60</top><width>36</width><height>36</height>
				<texture colordiffuse="FF4A9EFF">arrmada/spinner.png</texture>
				<visible>!String.IsEmpty(Window.Property(loading))</visible>
				<animation effect="rotate" end="-360" center="auto" time="900" loop="true" condition="true">Conditional</animation>
			</control>
		</control>
		<control type="grouplist" id="710">
			<left>1140</left><top>52</top><width>684</width><height>56</height>
			<orientation>horizontal</orientation>
			<itemgap>16</itemgap>
			<align>right</align>
			<ondown>720</ondown>
			<animation effect="slide" start="0,-40" end="0,0" time="450" tween="cubic" easing="out">WindowOpen</animation>
{button(T4, 711, "Pause sauf ce soir", 340)}
{button(T4, 712, "Tout reprendre", 260)}
		</control>

		<!-- ═══════════════ Pour ce soir ═══════════════ -->
		<control type="label">
			<left>96</left><top>176</top><width>360</width><height>48</height>
			<font>font15_bold</font>
			<textcolor>FFF5F7FA</textcolor>
			<aligny>center</aligny>
			<label>Pour ce soir</label>
		</control>
		<control type="label">
			<left>360</left><top>176</top><width>900</width><height>48</height>
			<font>font10</font>
			<textcolor>99C9D3E0</textcolor>
			<aligny>center</aligny>
			<label>Lancé depuis une TV : passe avant tout le reste</label>
		</control>
		<control type="list" id="720">
			<left>80</left><top>232</top><width>1760</width><height>300</height>
			<orientation>horizontal</orientation>
			<onup>710</onup>
			<ondown>700</ondown>
			<scrolltime tween="cubic" easing="out">300</scrolltime>
			<visible allowhiddenfocus="true">Integer.IsGreater(Container(720).NumItems,0)</visible>
			<animation type="Visible">
				<effect type="slide" start="0,60" end="0,0" time="500" tween="cubic" easing="out"/>
				<effect type="fade" start="0" end="100" time="400"/>
			</animation>
			<itemlayout width="880" height="300">
				<control type="group">
					<left>10</left><top>8</top>
{card(T5, False)}
				</control>
			</itemlayout>
			<focusedlayout width="880" height="300">
				<control type="group">
					<left>10</left><top>8</top>
					<animation effect="zoom" start="100" end="102" time="200" tween="cubic" easing="out" center="430,142">Focus</animation>
{card(T5, True)}
				</control>
			</focusedlayout>
		</control>
		<!-- Rien pour ce soir : l'emplacement reste, avec le mode d'emploi -->
		<control type="group">
			<left>90</left><top>240</top>
			<visible>!Integer.IsGreater(Container(720).NumItems,0) + String.IsEmpty(Window.Property(loading_first))</visible>
			<control type="image">
				<width>1740</width><height>200</height>
				<texture border="26" colordiffuse="0FFFFFFF">arrmada/rounded-24.png</texture>
			</control>
			<control type="label">
				<left>48</left><top>36</top><width>1640</width><height>56</height>
				<font>font15_bold</font>
				<textcolor>D9F5F7FA</textcolor>
				<aligny>center</aligny>
				<label>Rien pour ce soir</label>
			</control>
			<control type="label">
				<left>48</left><top>96</top><width>1640</width><height>70</height>
				<font>font12</font>
				<textcolor>99C9D3E0</textcolor>
				<wrapmultiline>true</wrapmultiline>
				<label>Lance un film ou un épisode depuis sa fiche, bouton Télécharger : il passera devant tous les autres téléchargements.</label>
			</control>
		</control>

		<!-- ═══════════════ File d'attente ═══════════════ -->
		<control type="label">
			<left>96</left><top>546</top><width>360</width><height>44</height>
			<font>font15_bold</font>
			<textcolor>FFF5F7FA</textcolor>
			<aligny>center</aligny>
			<label>File d'attente</label>
		</control>
		<control type="label">
			<left>360</left><top>546</top><width>900</width><height>44</height>
			<font>font10</font>
			<textcolor>99C9D3E0</textcolor>
			<aligny>center</aligny>
			<label>$INFO[Window.Property(queue_hint)]</label>
		</control>
		<control type="list" id="700">
			<left>80</left><top>594</top><width>1760</width><height>440</height>
			<orientation>vertical</orientation>
			<onup>720</onup>
			<scrolltime tween="cubic" easing="out">300</scrolltime>
			<visible allowhiddenfocus="true">Integer.IsGreater(Container(700).NumItems,0)</visible>
			<itemlayout width="1760" height="110">
{row(T4, False)}
			</itemlayout>
			<focusedlayout width="1760" height="110">
				<control type="group">
					<animation effect="zoom" start="100" end="101" time="200" tween="cubic" easing="out" center="880,55">Focus</animation>
{row(T5, True)}
				</control>
			</focusedlayout>
		</control>
		<control type="label">
			<left>96</left><top>640</top><width>1728</width><height>120</height>
			<font>font13</font>
			<textcolor>80C9D3E0</textcolor>
			<align>center</align><aligny>center</aligny>
			<label>$INFO[Window.Property(empty)]</label>
			<visible>!String.IsEmpty(Window.Property(empty))</visible>
		</control>
		<control type="label">
			<left>1024</left><top>1040</top><width>800</width><height>30</height>
			<font>font10</font>
			<textcolor>66C9D3E0</textcolor>
			<align>right</align><aligny>center</aligny>
			<label>OK : actions   ·   Retour : accueil</label>
		</control>
	</controls>
</window>
"""


def main(out: Path = OUT) -> None:
    out.write_text(render(), encoding="utf-8")
    print(f"OK : {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT)
