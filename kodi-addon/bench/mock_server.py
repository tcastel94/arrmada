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

STATE = {
    "tick": 0,
    "down": False,
    "qtick": 0,
    "paused": False,
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

    for idx, (name, _role) in enumerate(CAST[: len(PHOTO_COLORS)]):
        color = PHOTO_COLORS[idx]
        photo = _gradient((300, 300), color, (12, 14, 22))
        initials = "".join(part[0] for part in name.split()[:2])
        ImageDraw.Draw(photo).text((150, 160), initials, font=ImageFont.truetype(font_path, 120),
                                    fill=(255, 255, 255), anchor="mm")
        photo.save(out / f"photo-{idx}.jpg", quality=88)


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
                "overview": f"Synopsis de test pour « {title} » : une histoire épique, des "
                "personnages marquants et une mise en scène soignée.",
                "has_file": True,
            }
        )
    return items


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
        "youtube_trailer_id": "Way9Dexny3w" if idx == 0 else "",
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


def make_handler(base: str, images: Path, delay: float) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # journal sur stderr, préfixé
            sys.stderr.write("[mock] " + fmt % args + "\n")

        def _json(self, payload) -> None:
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
            time.sleep(delay)
            if STATE["down"]:
                self.send_error(503, "ArrMada en maintenance")
            elif path == "/api/kodi/addon-status":
                self._json({"status": "ok", "downloads": [], "downloads_count": 0, "recent_events": []})
            elif path == "/api/kodi/dashboard":
                self._json(dashboard())
            elif path == "/api/kodi/widgets/recent":
                self._json(recent(base))
            elif path.startswith("/api/media/"):
                _, _, _, kind, arr_id = path.split("/")[:5]
                payload = detail(base, kind, int(arr_id)) if arr_id.isdigit() else None
                if payload is None:
                    self.send_error(404)
                else:
                    self._json(payload)
            elif path == "/api/downloads":
                self._json(queue())
            elif path == "/api/yamaha/state":
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
                amp["sound_program"] = "straight" if data.get("room") == "salon" else "surr_decoder"
                self._json({"status": "ok", "room": data.get("room")})
            elif path.startswith("/api/kodi/downloads/"):
                STATE["paused"] = path.endswith("/pause")
                self._json({"status": "ok", "message": "ok"})
            elif path.startswith("/api/kodi/actions/"):
                self._json({"status": "ok", "message": "Demande envoyée (banc de test)"})
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
    server = ThreadingHTTPServer(("0.0.0.0", args.port), make_handler(args.base_url, images, args.delay))
    server.serve_forever()


if __name__ == "__main__":
    main()
