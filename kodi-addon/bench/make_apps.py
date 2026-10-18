#!/usr/bin/env python3
"""Applis & sources du banc (ADR-004, phase 4.3).

Fabrique, sans Internet :
  - les images du faux add-on vidéo (plugin.video.arrmadabanc) : icône,
    vignettes des vidéos ;
  - une TV en direct de test pour IPTV Simple : 3 chaînes (liste M3U) qui
    lisent le petit clip muet, leurs logos et un guide des programmes
    (XMLTV) calé sur l'heure du passage ;
  - un dossier « vidéos perso » (concerts, vacances) déclaré comme source.

Usage : python3 make_apps.py <dossier de sortie> <clip.mp4> <dossier de l'add-on de test>
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

CHANNELS = (
    ("banc1", "Banc Info", (20, 80, 160), ("Journal du banc", "Météo des serveurs")),
    ("banc2", "Banc Ciné", (150, 30, 60), ("Le Comte de Monte-Cristo", "Ciné-club")),
    ("banc3", "Banc Docs", (20, 120, 80), ("Les NAS de l'extrême", "Câbles et connecteurs")),
)
PERSO = ("Concert au Zénith (2025)", "Vacances en Bretagne", "Mariage de Julie")


def picture(path: str, size: tuple, color: tuple, text: str) -> None:
    """Fond uni + dégradé + texte centré : vignettes et logos de test."""
    width, height = size
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        shade = int(60 * y / max(1, height - 1))
        draw.line([(0, y), (width, y)], fill=tuple(max(0, c - shade) for c in color))
    box = draw.textbbox((0, 0), text)
    draw.text(
        ((width - (box[2] - box[0])) / 2, (height - (box[3] - box[1])) / 2),
        text,
        fill=(255, 255, 255),
    )
    image.save(path)


def link(clip: str, path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
    try:
        os.link(clip, path)
    except OSError:
        import shutil

        shutil.copy(clip, path)


def xmltv_time(moment: datetime) -> str:
    return moment.strftime("%Y%m%d%H%M%S +0000")


def main(out: str, clip: str, plugin_dir: str) -> None:
    clip = os.path.abspath(clip)
    for sub in ("thumbs", "logos", "iptv", "perso"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    # Faux add-on : icône (dans son dossier) + vignettes 16:9
    picture(os.path.join(plugin_dir, "icon.png"), (256, 256), (230, 70, 40), "BANC TV")
    for index in range(1, 7):
        hue = ((40 * index) % 200 + 30, 90, 200 - 25 * index)
        picture(os.path.join(out, "thumbs", f"video{index}.png"), (640, 360), hue, f"Video {index}")  # police par défaut de PIL : pas d'accents

    # TV en direct : logos, liste M3U (le clip comme flux), guide calé sur maintenant
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    m3u = ["#EXTM3U"]
    guide = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]
    for number, (cid, name, color, programmes) in enumerate(CHANNELS, start=1):
        logo = os.path.join(out, "logos", f"{cid}.png")
        picture(logo, (256, 144), color, name)
        m3u.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-chno="{number}" tvg-logo="{logo}" '
            f'group-title="Banc",{name}'
        )
        m3u.append(clip)
        guide.append(f'  <channel id="{cid}"><display-name>{name}</display-name></channel>')
        start = now - timedelta(minutes=10 * number)
        for title in programmes:
            stop = start + timedelta(minutes=45)
            guide.append(
                f'  <programme start="{xmltv_time(start)}" stop="{xmltv_time(stop)}" '
                f'channel="{cid}"><title>{title}</title>'
                f"<desc>{title} : programme de test du banc ArrMada.</desc></programme>"
            )
            start = stop
    guide.append("</tv>")
    with open(os.path.join(out, "iptv", "banc.m3u"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(m3u) + "\n")
    with open(os.path.join(out, "iptv", "banc.xml"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(guide) + "\n")

    # Vidéos perso (source « Dossiers »)
    for title in PERSO:
        link(clip, os.path.join(out, "perso", f"{title}.mp4"))
    print(f"OK : applis du banc dans {out}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
