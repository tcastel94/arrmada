#!/usr/bin/env python3
"""Médiathèque Kodi de test du banc (ADR-004, phase 4.1).

Crée une série (Severance, 2 saisons) et un film (Le Comte de Monte-Cristo),
avec leurs fiches .nfo et des images locales : le scraper « Informations
locales » de Kodi (metadata.local) les lit sans Internet. Titres et
identifiants (TVDB 371980…) sont ceux du faux serveur (mock_server.py) :
la Fiche ArrMada et l'écran Série retrouvent ainsi les titres dans Kodi.

Chaque vidéo est un lien physique vers un même petit clip muet (quelques Mo
en tout, au lieu de 15 copies).

Usage : python3 make_media.py <dossier médiathèque> <clip.mp4>
"""

from __future__ import annotations

import os
import shutil
import sys

from PIL import Image, ImageDraw

EPISODES = {
    1: [
        "Bonne nouvelle pour Kier",
        "Half Loop",
        "In Perpetuity",
        "The You You Are",
        "La Grande Bonté",
        "Hide and Seek",
        "Défi",
        "What's for Dinner?",
        "The We We Are",
    ],
    2: ["Bonjour, Mme Cobel", "Goodbye, Mrs. Selvig", "Who Is Alive?", "Woe's Hollow", "Trojan's Horse"],
}


def picture(path: str, size: tuple, top: tuple, bottom: tuple, text: str = "") -> None:
    """Dégradé vertical + texte : affiches, fonds et vignettes de test."""
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        draw.line([(0, y), (width, y)], fill=color)
    if text:
        draw.text((24, height - 48), text, fill=(255, 255, 255))
    image.save(path, quality=85)


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('<?xml version="1.0" encoding="UTF-8"?>\n' + text)


def video(clip: str, path: str) -> None:
    if os.path.exists(clip):
        os.link(clip, path)


def main(media: str, clip: str) -> None:
    shutil.rmtree(media, ignore_errors=True)

    show = os.path.join(media, "tv", "Severance (2022)")
    os.makedirs(show)
    write(
        os.path.join(show, "tvshow.nfo"),
        "<tvshow><title>Severance</title><premiered>2022-02-18</premiered>"
        "<plot>Les employés de Lumon ont accepté que leurs souvenirs professionnels et "
        "personnels soient séparés.</plot>"
        '<uniqueid type="tvdb" default="true">371980</uniqueid><genre>Drame</genre></tvshow>',
    )
    picture(os.path.join(show, "poster.jpg"), (400, 600), (60, 140, 160), (10, 30, 40), "SEVERANCE")
    picture(os.path.join(show, "fanart.jpg"), (1280, 720), (40, 100, 120), (8, 20, 30))
    for season, titles in EPISODES.items():
        folder = os.path.join(show, f"Season {season:02d}")
        os.makedirs(folder)
        for number, title in enumerate(titles, 1):
            base = os.path.join(folder, f"Severance - S{season:02d}E{number:02d}")
            video(clip, base + ".mp4")
            write(
                base + ".nfo",
                f"<episodedetails><title>{title}</title><season>{season}</season>"
                # Durée annoncée (minutes) : « Ce soir » calcule l'heure de fin (1.18)
                f"<episode>{number}</episode><runtime>2</runtime><aired>202{season + 1}-0{min(number, 9)}-1{number % 9}"
                f"</aired><plot>Saison {season}, épisode {number} : Mark et ses collègues "
                "découvrent un nouveau secret de Lumon.</plot></episodedetails>",
            )
            picture(
                base + "-thumb.jpg",
                (640, 360),
                (40 + number * 14, 70, 100 + season * 50),
                (10, 20, 30),
                f"S{season:02d}E{number:02d}",
            )

    movie = os.path.join(media, "movies", "Le Comte de Monte-Cristo (2024)")
    os.makedirs(movie)
    video(clip, os.path.join(movie, "Le Comte de Monte-Cristo (2024).mp4"))
    write(
        os.path.join(movie, "Le Comte de Monte-Cristo (2024).nfo"),
        "<movie><title>Le Comte de Monte-Cristo</title><year>2024</year><runtime>178</runtime>"
        "<plot>Edmond Dantès, accusé à tort, prépare sa vengeance.</plot>"
        '<uniqueid type="tmdb" default="true">1084736</uniqueid></movie>',
    )
    picture(os.path.join(movie, "poster.jpg"), (400, 600), (40, 70, 120), (10, 15, 30), "MONTE-CRISTO")
    print(f"Médiathèque de test : {media}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
