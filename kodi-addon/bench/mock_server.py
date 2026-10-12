#!/usr/bin/env python3
"""Faux backend ArrMada pour le banc de test Kodi (kodi-addon/bench/run.sh).

Répond comme le vrai backend aux routes lues par l'écran « Accueil » :
  GET /api/kodi/dashboard       indicateurs, disques, téléchargements, services
  GET /api/kodi/widgets/recent  ajouts récents (affiches, fanart, ClearLogo)
  GET /api/kodi/addon-status    utilisé par le service de l'add-on
  GET /api/media/{movie|series}/{id}  fiche complète (casting, fichier, saisons)
  GET /api/downloads            file complète (le « reste » diminue à chaque appel)
  GET /api/yamaha/state|profiles, POST /api/yamaha/control|preset/apply
                                faux ampli qui réagit aux commandes
  POST /api/kodi/actions/*, /api/kodi/downloads/*/pause|resume
  GET /img/<fichier>            images générées au démarrage (Pillow)
  GET /__down                   simule une panne : toutes les routes API → 503
  GET /__deny                   simule une TV refusée : toutes les routes API → 401
  GET /api/qr                   QR code vers la web app ou YouTube (phase 3)
  POST /api/devices/pair/confirm  appairage validé par mot de passe (migration)
  POST /api/kodi/scrobble       suivi de lecture de la TV (écran d'appoint, 1.10)
  GET /__scrobbles              ce que la TV a envoyé (vérifié par le harnais)
  GET|POST /api/kodi/watch-state  vu / reprise partagés entre les TV (phase 4.4)
  GET /__watch                  ce que la TV a déposé (vérifié par le harnais)
  GET /__watch_push?…           une « autre TV » change un état (+ événement)
  GET /api/kodi/series/371980/episodes  épisodes « Sonarr » de Severance
  GET /__room?room=bureau       la TV change de pièce dans la web app (1.19.1 :
                                bureau = pas d'ampli, /api/yamaha/state → no_amp)
  GET /__presets                préréglages d'ampli reçus (aucun depuis le bureau)

La progression des téléchargements avance à chaque appel, pour vérifier le
rafraîchissement en direct. Une latence est simulée (--delay) pour voir les
états de chargement. Usage local uniquement : aucune authentification.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

TB = 1024**4

# (titre, année, type, (résolution, plage dynamique, audio, canaux), couleurs de l'affiche)
# Un titre sans couleurs = sans affiche (teste le libellé de secours).
TITLES = [
    ("Dune : Deuxième partie", 2024, "movie", (2160, "DV HDR10", "TrueHD Atmos", 7.1), ((214, 140, 60), (60, 30, 20))),
    ("Shōgun", 2024, "series", (2160, "DV", "EAC3 Atmos", 5.1), ((150, 30, 30), (20, 10, 10))),
    ("Oppenheimer", 2023, "movie", (2160, "HDR10", "DTS-HD MA", 5.1), ((230, 120, 40), (30, 20, 40))),
    ("Le Comte de Monte-Cristo", 2024, "movie", (2160, "HDR10", "TrueHD Atmos", 7.1), ((40, 70, 120), (10, 15, 30))),
    ("Severance", 2022, "series", (2160, "DV", "EAC3", 5.1), ((60, 140, 160), (10, 30, 40))),
    ("Anatomie d'une chute", 2023, "movie", (1080, "", "AC3", 5.1), ((200, 200, 210), (40, 40, 50))),
    ("Arcane", 2021, "series", (2160, "HDR10", "EAC3", 5.1), ((120, 60, 200), (20, 10, 40))),
    ("Furiosa", 2024, "movie", (2160, "DV", "TrueHD Atmos", 7.1), ((230, 160, 60), (60, 20, 10))),
    ("The Bear", 2022, "series", (1080, "", "EAC3", 5.1), ((40, 90, 160), (10, 20, 40))),
    ("Blade Runner 2049", 2017, "movie", (2160, "HDR10", "TrueHD", 7.1), ((230, 90, 60), (40, 20, 60))),
    ("Titre sans affiche", 2025, "movie", (720, "", "AAC", 2), None),
    ("Interstellar", 2014, "movie", (2160, "HDR10", "DTS-HD MA", 5.1), ((180, 170, 150), (20, 20, 25))),
]

BOOT_ID = "banc-1"  # identifiant de démarrage, comme EventBus.boot_id

STATE = {
    "tick": 0,
    "down": False,
    "deny": False,  # /__deny : le serveur répond mais refuse la TV (401)
    "qtick": 0,
    "paused": False,
    "pair_polls": 0,
    "pair_confirmed": False,  # code validé avec le mot de passe (migration, phase 3)
    "read": set(),  # notifications marquées lues
    "events": [],  # événements relevés par l'add-on (déposés par /__emit)  # l'appairage est « validé dans la web app » au 3e poll
    "auth": "",  # dernier mode d'authentification vu (journal du banc)
    "scrobbles": [],  # suivi de lecture reçu de la TV (POST /api/kodi/scrobble)
    "watch": {},  # vu / reprise partagés : clé → état (avec « seq », le curseur)
    "watch_seq": 0,
    "watch_posts": [],  # dépôts reçus de la TV : {"merge", "states"}
    "presets": 0,  # POST /api/yamaha/preset/apply reçus (relus par /__presets)
    "amp": {"power": "on", "volume": 84, "mute": False, "input": "hdmi1", "sound_program": "surr_decoder"},
}
CAST = [
    ("Timothée Chalamet", "Paul Atréides"), ("Zendaya", "Chani"), ("Rebecca Ferguson", "Jessica"),
    ("Josh Brolin", "Gurney Halleck"), ("Austin Butler", "Feyd-Rautha"), ("Florence Pugh", "Irulan"),
    ("Javier Bardem", "Stilgar"), ("Léa Seydoux", "Margot Fenring"),
]
PHOTO_COLORS = [(214, 140, 60), (120, 60, 200), (60, 140, 160), (230, 90, 60), (40, 90, 160)]


# ── Images factices ──────────────────────────────────────────────────────────
# Visuels « plausibles » (lumières floues, grain, titrage) : ce sont eux qui
# apparaissent sur les captures, ils doivent ressembler à de vraies affiches.


def _gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(size[1]):
        t = y / size[1]
        draw.line([(0, y), (size[0], y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def _lights(img: Image.Image, rng: random.Random, color: tuple, count: int, blur: int) -> Image.Image:
    """Taches de lumière floues (effet « bokeh ») mélangées à l'image."""
    layer = Image.new("RGB", img.size, (0, 0, 0))
    draw = ImageDraw.Draw(layer)
    w, h = img.size
    for _ in range(count):
        r = rng.randint(w // 8, w // 3)
        x, y = rng.randint(0, w), rng.randint(0, int(h * 0.7))
        tint = tuple(min(255, int(c * rng.uniform(0.8, 1.3))) for c in color)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=tint)
    return ImageChops.screen(img, layer.filter(ImageFilter.GaussianBlur(blur)))


def _grain(img: Image.Image, rng: random.Random, amount: int = 14) -> Image.Image:
    noise = Image.effect_noise(img.size, amount).convert("RGB")
    return Image.blend(img, ImageChops.overlay(img, noise), 0.35)


def _vignette(img: Image.Image) -> Image.Image:
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse((-w * 0.25, -h * 0.2, w * 1.25, h * 1.15), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) // 6))
    return Image.composite(img, Image.new("RGB", (w, h), (0, 0, 0)), mask)


def make_images(out: Path, font_path: str) -> None:
    """Affiche (440×660), fanart (1280×720) et ClearLogo (PNG transparent) par titre."""
    out.mkdir(parents=True, exist_ok=True)
    for idx, (title, year, kind, _tech, colors) in enumerate(TITLES):
        if not colors:
            continue
        rng = random.Random(idx)  # images identiques d'un lancement à l'autre
        light, dark = colors

        # Affiche : dégradé, lumières, grain, vignettage, titrage et crédits
        poster = _gradient((440, 660), tuple(int(c * 0.55) for c in light), (8, 8, 12))
        poster = _lights(poster, rng, light, 5, 38)
        poster = _vignette(_grain(poster, rng))
        draw = ImageDraw.Draw(poster)
        draw.text((220, 46), "UN FILM ARRMADA" if kind == "movie" else "UNE SÉRIE ARRMADA",
                  font=ImageFont.truetype(font_path, 17), fill=(225, 225, 230), anchor="mm")
        words, lines, line = title.upper().split(), [], ""
        for word in words:
            if len(f"{line} {word}") > 12:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        lines.append(line)
        size = 62 if max(len(x) for x in lines) <= 9 else 48
        base = 470 - (len(lines) - 1) * size // 2
        for i, text in enumerate(lines):
            draw.text((220, base + i * (size + 4)), text, font=ImageFont.truetype(font_path, size),
                      fill=(250, 250, 250), anchor="mm")
        small = ImageFont.truetype(font_path, 11)
        for i in range(3):  # bloc de crédits, comme en bas des vraies affiches
            draw.text((220, 586 + i * 14), "RÉALISATION  ·  SCÉNARIO  ·  MUSIQUE  ·  PRODUCTION  ·  MONTAGE",
                      font=small, fill=(150, 150, 160), anchor="mm")
        draw.text((220, 636), f"{year}", font=ImageFont.truetype(font_path, 20),
                  fill=(235, 235, 240), anchor="mm")
        poster.save(out / f"poster-{idx}.jpg", quality=90)

        # Fanart : grandes lumières très floues + horizon lumineux + vignettage
        fanart = _gradient((1280, 720), tuple(int(c * 0.35) for c in light), dark)
        fanart = _lights(fanart, rng, light, 7, 90)
        horizon = Image.new("RGB", fanart.size, (0, 0, 0))
        ImageDraw.Draw(horizon).rectangle((0, 430, 1280, 470), fill=light)
        fanart = ImageChops.screen(fanart, horizon.filter(ImageFilter.GaussianBlur(60)))
        _vignette(_grain(fanart, rng, 10)).save(out / f"fanart-{idx}.jpg", quality=85)

        logo = Image.new("RGBA", (1200, 200), (0, 0, 0, 0))
        ImageDraw.Draw(logo).text((1190, 100), title.upper(), font=ImageFont.truetype(font_path, 64),
                                  fill=(255, 255, 255, 255), anchor="rm")
        logo.save(out / f"logo-{idx}.png")

        if idx in DISC_IDX:
            _disc(title, light, dark, font_path).save(out / f"disc-{idx}.png")

    for idx, (name, _role) in enumerate(CAST[: len(PHOTO_COLORS)]):
        color = PHOTO_COLORS[idx]
        photo = _gradient((300, 300), color, (12, 14, 22))
        initials = "".join(part[0] for part in name.split()[:2])
        ImageDraw.Draw(photo).text((150, 160), initials, font=ImageFont.truetype(font_path, 120),
                                    fill=(255, 255, 255), anchor="mm")
        photo.save(out / f"photo-{idx}.jpg", quality=88)


# Films qui ont un rond imprimé sur « fanart.tv » ; les autres (Anatomie d'une
# chute…) montrent le disque dessiné à partir de l'affiche.
DISC_IDX = {0, 2, 3, 7, 9, 11}


def _disc(title: str, light: tuple, dark: tuple, font_path: str) -> Image.Image:
    """Rond imprimé façon fanart.tv : PNG 1000 × 1000 transparent, trou central,
    moyeu translucide, titre et mention BLU-RAY sur la zone imprimée."""
    size, r = 1000, 498
    art = _gradient((size, size), light, dark).convert("RGBA")
    draw = ImageDraw.Draw(art)
    for k in range(6):  # anneaux décoratifs de l'impression
        rad = 420 - k * 6
        draw.ellipse((500 - rad, 500 - rad, 500 + rad, 500 + rad), outline=(255, 255, 255, 40), width=2)
    words = title.upper()
    font = ImageFont.truetype(font_path, 68 if len(words) <= 14 else 52)
    draw.text((500, 290), words, font=font, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((500, 770), "BLU-RAY DISC", font=ImageFont.truetype(font_path, 34),
              fill=(255, 255, 255, 220), anchor="mm")
    mask = Image.new("L", (size, size), 0)
    m = ImageDraw.Draw(mask)
    m.ellipse((500 - r, 500 - r, 500 + r, 500 + r), fill=255)
    hub = int(0.38 * r)
    m.ellipse((500 - hub, 500 - hub, 500 + hub, 500 + hub), fill=150)  # moyeu translucide
    hole = int(0.125 * r)
    m.ellipse((500 - hole, 500 - hole, 500 + hole, 500 + hole), fill=0)  # trou
    art.putalpha(mask)
    return art


# ── Réponses API ─────────────────────────────────────────────────────────────


def recent(base: str) -> list[dict]:
    items = []
    for idx, (title, year, kind, (res, hdr, audio, channels), colors) in enumerate(TITLES):
        items.append(
            {
                "external_id": str(100 + idx),
                "title": title,
                "year": year,
                "type": kind,
                "resolution": res,
                "video_dynamic_range": hdr,
                "audio_codec": audio,
                "audio_channels": channels,
                "poster_url": f"{base}/img/poster-{idx}.jpg" if colors else None,
                "fanart_url": f"{base}/img/fanart-{idx}.jpg" if colors else None,
                "clearlogo_url": f"{base}/img/logo-{idx}.png" if colors else None,
                "discart_url": f"{base}/img/disc-{idx}.png" if idx in DISC_IDX else None,
                "overview": f"Synopsis de test pour « {title} » : une histoire épique, des "
                "personnages marquants et une mise en scène soignée.",
                "has_file": True,
            }
        )
    return items


def calendar(base: str) -> dict:
    """À venir sur 7 jours, relatif à maintenant (épisodes à l'heure UTC, films à la date)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    episode = lambda idx, days, hour, label, season, number, sub: {  # noqa: E731
        "type": "episode", "title": TITLES[idx][0], "subtitle": sub, "label": label,
        "season": season, "episode": number, "series_id": 100 + idx, "network": "Apple TV+",
        "air_date": (now + timedelta(days=days)).replace(hour=hour).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "poster_url": f"{base}/img/poster-{idx}.jpg", "overview": f"Épisode « {sub} ».",
        "has_file": False,
    }
    movie = lambda idx, days, release: {  # noqa: E731
        "type": "movie", "title": TITLES[idx][0], "label": str(TITLES[idx][1]),
        "air_date": (now + timedelta(days=days)).strftime("%Y-%m-%d"), "release_type": release,
        "movie_id": 100 + idx, "poster_url": f"{base}/img/poster-{idx}.jpg",
        "overview": "Sortie de test.", "genres": ["Drama"], "has_file": False,
    }
    items = [
        episode(4, 0, 22, "S02E10", 2, 10, "Cold Harbor"),
        episode(6, 1, 1, "S02E04", 2, 4, "Les Rouages"),
        movie(7, 3, "digital"),
        episode(1, 5, 21, "S02E01", 2, 1, "Anjin"),
        movie(9, 6, "physical"),
    ]
    return {"start": "", "end": "", "total": len(items), "items": items, "by_date": {}}


def missing(base: str) -> dict:
    items = [dict(item, has_file=False, monitored=True) for item in recent(base)[6:10]]
    return {"items": items, "total": len(items)}


GENRES = ("Science Fiction", "Drama", "Adventure", "Comedy", "Animation", "Thriller")


def library(base: str) -> list[dict]:
    """Toute la bibliothèque (Films / Séries, 1.9.0) : le catalogue de test +
    130 films de remplissage, pour avoir plus d'une page (100 titres) de films."""
    items = []
    for idx, item in enumerate(recent(base)):
        items.append(dict(
            item,
            genres=[GENRES[idx % len(GENRES)], GENRES[(idx + 2) % len(GENRES)]],
            added=f"2026-10-{(idx % 9) + 1:02d}T12:00:00Z",
            size_bytes=(idx + 1) * 7_000_000_000,
            rating=6.5 + (idx % 4) / 2,
            monitored=True,
            has_file=idx not in (7, 11),  # deux films pas encore téléchargés
        ))
    for n in range(130):
        idx = n % 10
        items.append({
            "external_id": str(1000 + n),
            "title": f"Film de test {n + 1:03d}",
            "year": 1990 + n % 35,
            "type": "movie",
            "resolution": 2160 if n % 5 == 0 else 1080,
            "genres": [GENRES[n % len(GENRES)]],
            "poster_url": f"{base}/img/poster-{idx}.jpg",
            "fanart_url": f"{base}/img/fanart-{idx}.jpg",
            "overview": "Film de remplissage du banc de test.",
            "added": f"2025-0{(n % 9) + 1}-15T12:00:00Z",
            "size_bytes": 2_000_000_000 + n * 50_000_000,
            "rating": 5.0 + (n % 5),
            "monitored": True,
            "has_file": True,
        })
    return items


def lookup(base: str, term: str) -> list[dict]:
    """GET /api/kodi/media/lookup (recherche, 4.3) : titres suivis qui contiennent
    le terme, plus un résultat absent de la médiathèque (« Demander »)."""
    term = term.casefold().strip()
    out = []
    for item in library(base):
        if term and term in item["title"].casefold():
            series = item["type"] == "series"
            out.append({
                "title": item["title"], "year": item.get("year"), "type": item["type"],
                "tmdb_id": None if series else item.get("tmdb_id"),
                "tvdb_id": item.get("tmdb_id") if series else None,
                "overview": item.get("overview") or "", "poster_url": item.get("poster_url"),
                "in_library": True, "arr_id": int(item["external_id"]),
            })
    out.append({
        "title": f"{term.title()} : la série", "year": 2025, "type": "series", "tvdb_id": 999001,
        "overview": "Résultat absent de la médiathèque (banc) : OK ouvre « Demander ».",
        "poster_url": f"{base}/img/poster-3.jpg", "in_library": False, "arr_id": None,
    })
    return out


def media_page(base: str, query: dict) -> dict:
    """GET /api/media : mêmes filtres, tri et pagination que le vrai serveur."""
    media = library(base)
    if query.get("type"):
        media = [m for m in media if m["type"] == query["type"]]
    if query.get("availability") == "missing":
        media = [m for m in media if not m.get("has_file")]
    if query.get("genre"):
        media = [m for m in media if query["genre"] in m.get("genres", [])]
    if query.get("min_resolution"):
        media = [m for m in media if (m.get("resolution") or 0) >= int(query["min_resolution"])]
    key = {"size": "size_bytes"}.get(query.get("sort", "title"), query.get("sort", "title"))
    media.sort(key=lambda m: str(m.get(key) or "").casefold() if key == "title" else m.get(key) or 0,
               reverse=query.get("order") == "desc")
    page, per_page = int(query.get("page") or 1), int(query.get("per_page") or 50)
    total = len(media)
    return {
        "items": media[(page - 1) * per_page:page * per_page],
        "pagination": {"page": page, "per_page": per_page, "total": total,
                       "total_pages": max(1, (total + per_page - 1) // per_page)},
    }


def media_facets(base: str, kind: str) -> dict:
    counts: dict = {}
    for m in library(base):
        if not kind or m["type"] == kind:
            for genre in m.get("genres", []):
                counts[genre] = counts.get(genre, 0) + 1
    return {"genres": sorted(counts), "genre_counts": counts, "qualities": [], "total": 0}


def recommendations(base: str) -> dict:
    def tmdb(idx: int, in_library: bool = False) -> dict:
        title, year, kind, _, _ = TITLES[idx]
        return {
            "tmdb_id": 5000 + idx, "title": title, "type": kind, "year": str(year),
            "overview": f"Recommandation de test : « {title} ».", "rating": 7.1 + idx / 10,
            "poster_url": f"{base}/img/poster-{idx}.jpg",
            "backdrop_url": f"{base}/img/fanart-{idx}.jpg", "in_library": in_library,
        }

    return {
        "because_you_have": [
            {"base_title": "Dune : Deuxième partie", "recommendations": [tmdb(2), tmdb(11)]},
            {"base_title": "Severance", "recommendations": [tmdb(5)]},
        ],
        "trending_movies": [tmdb(7), tmdb(0, in_library=True), tmdb(9)],
        "trending_series": [tmdb(6), tmdb(1, in_library=True)],
        "wanted": [],
        "tmdb_available": True,
    }


def watch_key(state: dict) -> str:
    key = f"{state.get('media_type')}:{state.get('id_type')}:{state.get('id')}"
    if state.get("media_type") == "episode":
        key += f":{int(state.get('season') or 0)}:{int(state.get('episode') or 0)}"
    return key


def watch_store(states: list, device: str) -> int:
    """Range des états (le plus récent gagne) ; publie `watch_state` si l'un change."""
    changed = 0
    for raw in states:
        key = watch_key(raw)
        old = STATE["watch"].get(key)
        if old and bool(old["watched"]) == bool(raw.get("watched")) and abs(
            int(old["position"] or 0) - int(raw.get("position") or 0)
        ) < 10:
            continue
        # Curseur en microsecondes, toujours croissant comme les dates du vrai
        # serveur : une TV qui garde le curseur d'un banc précédent (profil
        # conservé) voit quand même les états de ce banc-ci.
        STATE["watch_seq"] = max(STATE["watch_seq"] + 1, int(time.time() * 1_000_000))
        STATE["watch"][key] = dict(raw, device=device, seq=STATE["watch_seq"])
        changed += 1
    if changed:
        STATE["events"].append(
            (len(STATE["events"]) + 1, "watch_state", {"changed": changed, "device": device})
        )
    return changed


def sonarr_episodes() -> list:
    """Severance vue par « Sonarr » : la médiathèque du banc a S01 (9) et S02E01-05.

    S02E06 diffusé sans fichier (manquant), S02E07 téléchargé mais pas encore
    dans Kodi, S02E08-10 à venir (dates autour du jour du banc), S03E01 sans date.
    """
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    episodes = [
        {"season": 1, "episode": n, "title": f"S1 {n}", "air_date": "2022-02-18T02:00:00Z",
         "has_file": True, "monitored": True, "overview": ""}
        for n in range(1, 10)
    ]  # fmt: skip
    episodes += [
        {"season": 2, "episode": n, "title": f"S2 {n}", "air_date": "2025-01-17T02:00:00Z",
         "has_file": True, "monitored": True, "overview": ""}
        for n in range(1, 6)
    ]  # fmt: skip
    titles = {6: "Attila", 7: "Chikhai Bardo", 8: "Sweet Vitriol", 9: "The After Hours",
              10: "Cold Harbor"}  # fmt: skip
    for n in range(6, 11):
        if n <= 7:
            air = (now - timedelta(days=30 - n)).isoformat()
        else:
            air = (now + timedelta(days=7 * (n - 7))).isoformat()
        episodes.append({
            "season": 2, "episode": n, "title": titles[n], "air_date": air,
            "has_file": n == 7, "monitored": True,
            "overview": "Épisode connu de Sonarr, absent de la médiathèque Kodi du banc.",
        })  # fmt: skip
    episodes.append({"season": 3, "episode": 1, "title": "TBA", "air_date": "",
                     "has_file": False, "monitored": True, "overview": ""})  # fmt: skip
    return episodes


def notifications() -> dict:
    from datetime import datetime, timedelta, timezone

    def stamp(minutes: int) -> str:  # heure UTC sans fuseau, comme le vrai serveur
        moment = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        return moment.replace(tzinfo=None).isoformat()

    items = [
        {"id": 3, "type": "import", "severity": "info", "title": "Dune : Deuxième partie importé",
         "message": "Remux-2160p · 64 Go, prêt dans la médiathèque.", "is_read": 3 in STATE["read"],
         "service_name": "Radarr", "created_at": stamp(4)},
        {"id": 2, "type": "health", "severity": "warning", "title": "Indexeur lent",
         "message": "NZBgeek répond en plus de 8 s.", "is_read": 2 in STATE["read"],
         "service_name": "Prowlarr", "created_at": stamp(150)},
        {"id": 1, "type": "grab", "severity": "info", "title": "Arcane S02E09 lancé",
         "message": "WEBDL-2160p via SABnzbd.", "is_read": True,
         "service_name": "Sonarr", "created_at": stamp(60 * 30)},
    ]
    unread = sum(1 for item in items if not item["is_read"])
    return {"items": items, "unread_count": unread}


def dashboard() -> dict:
    STATE["tick"] += 1
    tick = STATE["tick"]
    return {
        "status": "ok",
        "stats": {"movies_count": 3412, "series_count": 186, "episodes_count": 12044,
                  "total_size_human": "42,1 To"},
        # Même disque vu par Radarr et Sonarr : l'add-on doit le compter une fois.
        "disks": [
            {"path": "/mnt/user/media", "total_bytes": 60 * TB, "free_bytes": 13 * TB},
            {"path": "/mnt/user/media", "total_bytes": 60 * TB, "free_bytes": 13 * TB},
        ],
        "downloads": [
            {"id": 1, "title": "Gladiator.II.2024.2160p.UHD.BluRay.REMUX.DV.HDR10.TrueHD.Atmos",
             "progress": min(99, 62 + tick * 3), "timeleft": "00:12:30", "service": "radarr"},
            {"id": 2, "title": "The.Penguin.S01E08.1080p.WEB.H264",
             "progress": min(99, 24 + tick * 5), "timeleft": "00:41:10", "service": "sonarr"},
            {"id": 3, "title": "Wicked.2024.2160p.WEB-DL.DV.HDR.DDP5.1.Atmos",
             "progress": 8, "timeleft": "1.02:15:00", "service": "radarr"},
            {"id": 4, "title": "Silo.S02E05.2160p.WEB.H265", "progress": 2, "timeleft": "",
             "service": "sonarr"},
        ],
        "downloads_count": 4,
        "services": [
            {"name": "Radarr", "type": "radarr", "is_enabled": True},
            {"name": "Sonarr", "type": "sonarr", "is_enabled": True},
            {"name": "Prowlarr", "type": "prowlarr", "is_enabled": True},
            {"name": "SABnzbd", "type": "sabnzbd", "is_enabled": True},
            {"name": "Bazarr", "type": "bazarr", "is_enabled": True},
            {"name": "Jellyseerr", "type": "jellyseerr", "is_enabled": False},
        ],
    }


def episodes(season: int, count: int, have: int) -> dict:
    """Saison façon Sonarr : les `have` premiers épisodes ont un fichier."""
    return {
        "season_number": season,
        "episode_count": count,
        "episodes_have": have,
        "episodes": [
            {
                "episode_number": n,
                "season_number": season,
                "has_file": n <= have,
                "file": {
                    "quality": "WEBDL-2160p",
                    "resolution": 2160,
                    "size_bytes": 4 * 1024**3,
                    "video_codec": "HEVC",
                    "video_dynamic_range_type": "DV HDR10",
                    "audio_codec": "EAC3 Atmos",
                    "audio_channels": 6,
                    "audio_languages": "Anglais / Français",
                }
                if n <= have
                else None,
            }
            for n in range(1, count + 1)
        ],
    }


def detail(base: str, kind: str, arr_id: int) -> dict | None:
    """Fiche façon /api/media/{movie|series}/{id} pour les titres de TITLES."""
    idx = arr_id - 100
    if not 0 <= idx < len(TITLES):
        return None
    title, year, item_kind, (res, hdr, audio, channels), colors = TITLES[idx]
    images = {
        "poster": f"{base}/img/poster-{idx}.jpg" if colors else None,
        "fanart": f"{base}/img/fanart-{idx}.jpg" if colors else None,
        "clearlogo": f"{base}/img/logo-{idx}.png" if colors else None,
        "discart": f"{base}/img/disc-{idx}.png" if idx in DISC_IDX else None,
        "disc_type": "bluray" if idx in DISC_IDX else None,
    }
    common = {
        "id": arr_id,
        "title": title,
        "year": year,
        "overview": f"Synopsis de test pour « {title} ». Un récit ambitieux porté par une distribution "
        "remarquable, une photographie spectaculaire et une bande originale envoûtante. "
        "Le texte est volontairement long pour vérifier le défilement automatique du synopsis "
        "dans la fiche, comme sur un vrai titre de la médiathèque.",
        "genres": ["Science Fiction", "Adventure", "Drama"],
        "images": images,
        "certification": "PG-13",
    }
    if kind == "series" or item_kind == "series":
        return {
            **common,
            "type": "series",
            "runtime": 55,
            "network": "Apple TV+",
            "tvdb_id": 371980,
            "episodes_have": 15,
            "total_episodes": 19,
            "status": "continuing",
            "size_on_disk": 61 * 1024**3,
            "ratings": {"value": 8.7},
            "seasons": [
                episodes(1, 9, 9),
                episodes(2, 10, 6),
                episodes(3, 8, 0),
            ],
            "subtitles": [{"language": "Français"}, {"language": "Anglais"}],
        }
    return {
        **common,
        "type": "movie",
        "runtime": 166,
        "has_file": True,
        "tmdb_id": 693134 + idx,
        # Tous les films ont une bande-annonce : sans l'add-on YouTube (cas du
        # banc), la fiche affiche son QR code (phase 3).
        "youtube_trailer_id": "Way9Dexny3w",
        "ratings": {"tmdb": 8.2, "imdb": 8.6, "rotten_tomatoes": 92},
        "file": {
            "quality": "Remux-2160p" if res >= 2160 else "WEBDL-1080p",
            "resolution": res,
            "size_bytes": 64 * 1024**3,
            "video_codec": "HEVC",
            "video_dynamic_range_type": hdr,
            "audio_codec": audio,
            "audio_channels": channels,
            "audio_languages": "Français / Anglais",
            "release_group": "FraMeSToR",
        },
        "cast": [
            {"name": name, "character": role,
             "photo": f"{base}/img/photo-{i}.jpg" if i < len(PHOTO_COLORS) else None}
            for i, (name, role) in enumerate(CAST)
        ],
        "crew": [
            {"name": "Denis Villeneuve", "job": "Director"},
            {"name": "Hans Zimmer", "job": "Original Music Composer"},
        ],
        "subtitles": [{"language": "Français"}, {"language": "Anglais"}],
    }


def queue() -> dict:
    """File complète : le « reste » diminue de ~180 Mo par appel (débit visible)."""
    STATE["qtick"] += 1
    t = STATE["qtick"]
    GB = 1024**3
    downloading = "paused" if STATE["paused"] else "downloading"

    def item(i, service, title, size, done, quality, extra=None):
        left = max(0, size - done - (0 if STATE["paused"] else t * 180 * 1024**2))
        return {
            "id": 500 + i,
            "service_type": service,
            "title": title,
            "status": downloading,
            "tracked_state": "downloading",
            "progress": round((size - left) * 100 / size, 1),
            "size_bytes": size,
            "size_left_bytes": left,
            "time_left": "00:12:30",
            "download_client": "SABnzbd",
            "protocol": "usenet",
            "quality": quality,
            "indexer": "NZBgeek",
            "movie_id": 100 + i if service == "radarr" else None,
            "series_id": 104 if service == "sonarr" else None,
            **(extra or {}),
        }

    items = [
        item(0, "radarr", "Gladiator.II.2024.2160p.UHD.BluRay.REMUX.DV.HDR10.TrueHD.Atmos", 78 * GB, 48 * GB, "Remux-2160p"),
        item(1, "sonarr", "The.Penguin.S01E08.1080p.WEB.H264", 3 * GB, 1 * GB, "WEBDL-1080p"),
        item(2, "radarr", "Wicked.2024.2160p.WEB-DL.DV.HDR.DDP5.1.Atmos", 22 * GB, 2 * GB, "WEBDL-2160p",
             {"time_left": "1.02:15:00"}),
        item(3, "sonarr", "Silo.S02E05.2160p.WEB.H265", 6 * GB, 0, "WEBDL-2160p",
             {"status": "queued", "tracked_state": "queued", "time_left": ""}),
        item(4, "radarr", "Nosferatu.2024.1080p.BluRay.x264", 12 * GB, 12 * GB, "Bluray-1080p",
             {"status": "completed", "tracked_state": "importPending", "time_left": ""}),
        item(5, "sonarr", "Shogun.S01E10.2160p.WEB.H265", 7 * GB, 7 * GB, "WEBDL-2160p",
             {"status": "warning", "tracked_state": "importBlocked", "time_left": "",
              "error": "Import bloqué : épisode déjà présent avec une meilleure qualité"}),
    ]
    return {"items": items, "total": len(items)}


def yamaha_state() -> dict:
    amp = STATE["amp"]
    return {"devices": [{
        "id": 1, "name": "Yamaha RX-A2080", "online": True, "power": amp["power"],
        "volume": amp["volume"], "max_volume": 161, "volume_pct": round(amp["volume"] * 100 / 161),
        "mute": amp["mute"], "input": amp["input"], "actual_db": -80.5 + amp["volume"] * 0.5,
        "sound_program": amp["sound_program"],
    }]}


PAIR_CODE = "K7P4QX"
PAIRED_DEVICE = {
    "id": 1, "name": "Shield Salon", "room": "salon", "avr_name": "Yamaha RX-A2080", "has_amp": True,
}
ROOMS = {  # pièce → (nom de l'appareil, ampli) comme le vrai serveur (1.19.1)
    "salon": ("Shield Salon", "Yamaha RX-A2080"),
    "bureau": ("TV Sony Bureau", None),
}


def make_qr(path: Path, text: str) -> None:
    """QR code de la page d'appairage (segno si présent, sinon un faux motif)."""
    try:
        import segno

        segno.make(text, error="m").save(str(path), kind="png", scale=10, border=4)
        return
    except ImportError:
        pass
    rng = random.Random(7)
    size, cell = 33, 10
    img = Image.new("RGB", ((size + 8) * cell,) * 2, "white")
    draw = ImageDraw.Draw(img)

    def finder(x: int, y: int) -> bool | None:
        """Les 3 carrés de repérage d'un QR code (anneau clair à distance 2)."""
        for fx, fy in ((0, 0), (size - 7, 0), (0, size - 7)):
            if fx <= x < fx + 7 and fy <= y < fy + 7:
                return max(abs(x - fx - 3), abs(y - fy - 3)) != 2
        return None

    for y in range(size):
        for x in range(size):
            dark = finder(x, y)
            if dark is None:
                dark = rng.random() < 0.5
            if dark:
                x0, y0 = (x + 4) * cell, (y + 4) * cell
                draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill="black")
    img.save(path)


def make_handler(base: str, images: Path, delay: float) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # journal sur stderr, préfixé
            sys.stderr.write("[mock] " + fmt % args + "\n")

        def _json(self, payload, status: int = 200) -> None:
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _note_auth(self) -> None:
            """Journalise le passage du mot de passe admin au jeton d'appareil."""
            mode = (
                "device"
                if self.headers.get("X-Device-Token")
                else "api_key"
                if self.headers.get("X-Api-Key")
                else "none"
            )
            if mode != STATE["auth"]:
                sys.stderr.write(f"[mock] authentification : {mode}\n")
                STATE["auth"] = mode

        def _qr(self, head: bool) -> None:
            data = (images / "pair-qr.png").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not head:
                self.wfile.write(data)

        def do_HEAD(self):  # noqa: N802 — Kodi interroge les images en HEAD
            path = self.path.split("?")[0]
            if path == f"/api/devices/pair/qr/{PAIR_CODE}.png":
                self._qr(head=True)
            elif path.startswith("/img/") and (images / Path(path[5:]).name).is_file():
                file = images / Path(path[5:]).name
                self.send_response(200)
                self.send_header("Content-Type", "image/png" if file.suffix == ".png" else "image/jpeg")
                self.send_header("Content-Length", str(file.stat().st_size))
                self.end_headers()
            else:
                self.send_error(404)

        def do_GET(self):  # noqa: N802 (nom imposé par http.server)
            path = self.path.split("?")[0]
            if path.startswith("/img/"):
                file = images / Path(path[5:]).name  # pas de « ../ » possible
                if not file.is_file():
                    self.send_error(404)
                    return
                data = file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png" if file.suffix == ".png" else "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/__down":
                STATE["down"] = True
                self._json({"down": True})
                return
            if path == "/__deny":
                STATE["down"], STATE["deny"] = False, True
                self._json({"deny": True})
                return
            if path == "/__scrobbles":  # le harnais relit le suivi de lecture reçu
                self._json(STATE["scrobbles"])
                return
            if path == "/__watch":  # le harnais relit les états vu / reprise déposés
                self._json({"posts": STATE["watch_posts"], "states": list(STATE["watch"].values())})
                return
            if path == "/__watch_push":  # une « autre TV » change un état
                from urllib.parse import parse_qs, urlsplit

                query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                state = {
                    "media_type": query.get("media_type", "episode"),
                    "id_type": query.get("id_type", "tvdb"),
                    "id": query.get("id", "371980"),
                    "season": int(query.get("season", 0)),
                    "episode": int(query.get("episode", 0)),
                    "title": query.get("title", ""),
                    "watched": query.get("watched") == "1",
                    "position": int(query.get("position", 0)),
                    "total": int(query.get("total", 90)),
                    "last_played": query.get("last_played", ""),
                }
                self._json({"changed": watch_store([state], "Shield Cinéma")})
                return
            if path == "/__room":  # la TV change de pièce dans la web app (1.19.1)
                from urllib.parse import parse_qs, urlsplit

                room = parse_qs(urlsplit(self.path).query).get("room", ["salon"])[0]
                name, avr = ROOMS.get(room, ROOMS["salon"])
                PAIRED_DEVICE.update(name=name, room=room, avr_name=avr, has_amp=avr is not None)
                self._json(PAIRED_DEVICE)
                return
            if path == "/__presets":  # préréglages d'ampli reçus
                self._json({"presets": STATE["presets"]})
                return
            if path == "/__emit":  # le harnais publie un événement temps réel
                from urllib.parse import parse_qs, urlsplit

                query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                event_type = query.pop("type", "new_import")
                STATE["events"].append((len(STATE["events"]) + 1, event_type, query))
                self._json({"queued": event_type})
                return
            time.sleep(delay)
            self._note_auth()
            if STATE["down"]:
                self.send_error(503, "ArrMada en maintenance")
            elif STATE["deny"] and path.startswith("/api/"):
                self._json({"detail": "Not authenticated"}, status=401)
            elif path == f"/api/devices/pair/qr/{PAIR_CODE}.png":
                self._qr(head=False)
            elif path == "/api/devices/me":
                paired = STATE["auth"] == "device"
                self._json({"paired": paired, **(PAIRED_DEVICE if paired else {})})
            elif path == "/api/kodi/addon-status":
                self._json({"status": "ok", "downloads": [], "downloads_count": 0, "recent_events": []})
            elif path == "/api/kodi/dashboard":
                self._json(dashboard())
            elif path == "/api/kodi/widgets/recent":
                self._json(recent(base))
            elif path.startswith("/api/media/") and path != "/api/media/facets":
                _, _, _, kind, arr_id = path.split("/")[:5]
                payload = detail(base, kind, int(arr_id)) if arr_id.isdigit() else None
                if payload is None:
                    self.send_error(404)
                else:
                    self._json(payload)
            elif path == "/api/downloads":
                self._json(queue())
            elif path == "/api/calendar":
                self._json(calendar(base))
            elif path == "/api/media":
                from urllib.parse import parse_qs, urlsplit

                query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                if query.get("availability") == "missing" and query.get("monitored"):
                    self._json(missing(base))  # flux « Manquants » (service)
                else:
                    self._json(media_page(base, query))  # Films / Séries (1.9.0)
            elif path == "/api/kodi/media/lookup":
                from urllib.parse import parse_qs, urlsplit

                query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                self._json(lookup(base, query.get("q", "")))
            elif path == "/api/media/facets":
                from urllib.parse import parse_qs, urlsplit

                query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                self._json(media_facets(base, query.get("type", "")))
            elif path == "/api/recommendations":
                self._json(recommendations(base))
            elif path == "/api/notifications":
                self._json(notifications())
            elif path == "/api/events/recent":
                # Relevé toutes les 5 s par le service de l'add-on, comme le vrai serveur
                from urllib.parse import parse_qs, urlsplit

                since = int((parse_qs(urlsplit(self.path).query).get("since_id") or ["0"])[0])
                self._json({
                    "events": [
                        {"id": i, "type": t, "data": d, "timestamp": 0}
                        for i, t, d in STATE["events"] if i > since
                    ],
                    "clients": 0,
                    "boot_id": BOOT_ID,
                    "last_id": len(STATE["events"]),
                })
            elif path == "/api/kodi/watch-state":
                from urllib.parse import parse_qs, urlsplit

                query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                since = int(query.get("since") or 0)
                limit = int(query.get("limit") or 500)
                rows = sorted(
                    (s for s in STATE["watch"].values() if s["seq"] > since), key=lambda s: s["seq"]
                )
                page = rows[:limit]
                self._json({
                    "states": [dict(s, updated_at=str(s["seq"])) for s in page],
                    "cursor": str(page[-1]["seq"]) if page else (query.get("since") or ""),
                    "more": len(rows) > limit,
                })
            elif path == "/api/kodi/series/371980/episodes":
                self._json({"status": "ok", "title": "Severance", "episodes": sonarr_episodes()})
            elif path.startswith("/api/kodi/series/") and path.endswith("/episodes"):
                self._json({"status": "unknown", "episodes": []})
            elif path.startswith("/api/cameras/snapshot/"):
                # Photo d'une détection Eufy (pop-up de la TV), en base64 comme le serveur
                import base64

                photo = images / "fanart-4.jpg"
                if photo.is_file():
                    self._json({"mime": "image/jpeg",
                                "image": base64.b64encode(photo.read_bytes()).decode()})
                else:
                    self.send_error(404)
            elif path == "/api/qr":
                # QR code vers la web app ou YouTube (phase 3), comme le vrai serveur
                import base64
                import hashlib
                from urllib.parse import parse_qs, urlsplit

                query = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
                if query.get("youtube"):
                    url = f"https://www.youtube.com/watch?v={query['youtube']}"
                else:
                    url = f"http://192.168.2.3:3420{query.get('path') or '/'}"
                file = images / f"qr-{hashlib.sha1(url.encode()).hexdigest()[:10]}.png"
                if not file.exists():
                    make_qr(file, url)
                self._json({"url": url, "png": base64.b64encode(file.read_bytes()).decode()})
            elif path == "/api/yamaha/state":
                if STATE["auth"] == "device" and not PAIRED_DEVICE["has_amp"]:
                    # TV du bureau : comme le vrai serveur, jamais l'ampli du salon
                    self._json({"devices": [], "status": "no_amp", "detail": "Pas d'ampli dans cette pièce"})
                else:
                    self._json(yamaha_state())
            elif path == "/api/yamaha/profiles":
                self._json({"salon": {"name": "Salon"}, "cinema": {"name": "Salle de cinéma"}})
            else:
                self.send_error(404)

        def do_POST(self):  # noqa: N802
            path = self.path.split("?")[0]
            length = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                data = {}
            time.sleep(delay / 2)
            amp = STATE["amp"]
            if STATE["down"]:
                self.send_error(503, "ArrMada en maintenance")
            elif path.startswith("/api/notifications/") and path.endswith("/read"):
                STATE["read"].add(int(path.split("/")[3]))
                self._json({"success": True})
            elif path == "/api/devices/pair/start":
                STATE["pair_polls"] = 0
                STATE["pair_confirmed"] = False
                self._json({
                    "device_code": "code-secret-du-banc",
                    "user_code": PAIR_CODE,
                    "verification_url": f"http://192.168.2.3:3420/settings/kodi?pair={PAIR_CODE}",
                    "qr_url": f"/api/devices/pair/qr/{PAIR_CODE}.png",
                    "expires_in": 600,
                    "interval": 3,
                })
            elif path == "/api/devices/pair/confirm":
                # Migration de l'ancien mot de passe (phase 3) : la TV valide
                # elle-même son code, avec le mot de passe en X-Api-Key.
                if not self.headers.get("X-Api-Key"):
                    self._json({"detail": "Not authenticated"}, status=401)
                else:
                    STATE["pair_confirmed"] = True
                    sys.stderr.write(f"[mock] appairage validé par mot de passe : {data}\n")
                    self._json({"status": "ok", "device": PAIRED_DEVICE})
            elif path == "/api/devices/pair/poll":
                STATE["pair_polls"] += 1
                if STATE["pair_polls"] < 3 and not STATE["pair_confirmed"]:
                    self._json({"status": "pending", "interval": 3})
                else:
                    self._json({"status": "ok", "token": "jeton-du-banc", "device": PAIRED_DEVICE})
            elif path == "/api/yamaha/control":
                action, value = data.get("action"), data.get("value")
                if action == "volume_step":
                    amp["volume"] = max(0, min(161, amp["volume"] + int(value)))
                elif action == "mute":
                    amp["mute"] = bool(value)
                elif action == "power":
                    amp["power"] = "standby" if value == "standby" else "on"
                self._json({"status": "ok", "action": action})
            elif path == "/api/yamaha/preset/apply":
                STATE["presets"] += 1
                sys.stderr.write(f"[mock] préréglage d'ampli reçu : {data}\n")
                amp["sound_program"] = "straight" if data.get("room") == "salon" else "surr_decoder"
                self._json({"status": "ok", "room": data.get("room")})
            elif path.startswith("/api/kodi/downloads/"):
                STATE["paused"] = path.endswith("/pause")
                self._json({"status": "ok", "message": "ok"})
            elif path.startswith("/api/kodi/actions/"):
                self._json({"status": "ok", "message": "Demande envoyée (banc de test)"})
            elif path == "/api/kodi/watch-state":
                states = data.get("states") or []
                STATE["watch_posts"].append({"merge": bool(data.get("merge")), "states": states})
                sys.stderr.write(
                    f"[mock] vu / reprise : {len(states)} état(s) "
                    f"({'fusion' if data.get('merge') else 'direct'})\n"
                )
                if data.get("merge"):
                    # Premier passage : « vu » l'emporte, rien n'est défait
                    fresh = [s for s in states if watch_key(s) not in STATE["watch"]]
                    changed = watch_store(fresh, "Kodi du banc")
                else:
                    changed = watch_store(states, "Kodi du banc")
                self._json({"status": "ok", "changed": changed, "rejected": 0, "cursor": ""})
            elif path == "/api/kodi/scrobble":
                STATE["scrobbles"].append(data)
                sys.stderr.write(f"[mock] lecture : {json.dumps(data, ensure_ascii=False)}\n")
                self._json({"status": "ok"})
            else:
                self.send_error(404)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True, help="URL publique du faux backend (images)")
    parser.add_argument("--font", required=True, help="police TTF pour dessiner les images")
    parser.add_argument("--images", default="img", help="dossier des images générées")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--delay", type=float, default=0.6, help="latence simulée (s)")
    args = parser.parse_args()

    images = Path(args.images)
    make_images(images, args.font)
    make_qr(images / "pair-qr.png", f"http://192.168.2.3:3420/settings/kodi?pair={PAIR_CODE}")
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(args.base_url, images, args.delay))
    server.serve_forever()


if __name__ == "__main__":
    main()
