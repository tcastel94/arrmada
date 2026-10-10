#!/usr/bin/env python3
"""Faux backend ArrMada pour le banc de test Kodi (kodi-addon/bench/run.sh).

Répond comme le vrai backend aux routes lues par l'écran « Accueil » :
  GET /api/kodi/dashboard       indicateurs, disques, téléchargements, services
  GET /api/kodi/widgets/recent  ajouts récents (affiches, fanart, ClearLogo)
  GET /api/kodi/addon-status    utilisé par le service de l'add-on
  GET /img/<fichier>            images générées au démarrage (Pillow)
  GET /__down                   simule une panne : toutes les routes API → 503

La progression des téléchargements avance à chaque appel, pour vérifier le
rafraîchissement en direct. Une latence est simulée (--delay) pour voir les
états de chargement. Usage local uniquement : aucune authentification.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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

STATE = {"tick": 0, "down": False}


# ── Images factices ──────────────────────────────────────────────────────────


def _gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(size[1]):
        t = y / size[1]
        draw.line([(0, y), (size[0], y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return img


def make_images(out: Path, font_path: str) -> None:
    """Affiche (440×660), fanart (1280×720) et ClearLogo (PNG transparent) par titre."""
    out.mkdir(parents=True, exist_ok=True)
    for idx, (title, year, _kind, _tech, colors) in enumerate(TITLES):
        if not colors:
            continue
        poster = _gradient((440, 660), *colors)
        draw = ImageDraw.Draw(poster)
        draw.ellipse((120, 120, 320, 320), outline=(255, 255, 255), width=6)
        lines, line = [], ""
        for word in title.split():
            if len(f"{line} {word}") > 14:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        lines.append(line)
        for i, text in enumerate(lines):
            draw.text((220, 430 + i * 54), text.upper(), font=ImageFont.truetype(font_path, 46),
                      fill=(255, 255, 255), anchor="mm")
        draw.text((220, 620), str(year), font=ImageFont.truetype(font_path, 30),
                  fill=(230, 230, 230), anchor="mm")
        poster.save(out / f"poster-{idx}.jpg", quality=90)

        fanart = _gradient((1280, 720), colors[0], colors[1]).filter(ImageFilter.GaussianBlur(4))
        fdraw = ImageDraw.Draw(fanart)
        for k in range(9):
            fdraw.ellipse((700 + k * 40, 80 + k * 25, 1100 + k * 40, 480 + k * 25),
                          outline=(255, 255, 255), width=2)
        fanart.save(out / f"fanart-{idx}.jpg", quality=85)

        logo = Image.new("RGBA", (1200, 200), (0, 0, 0, 0))
        ImageDraw.Draw(logo).text((1190, 100), title.upper(), font=ImageFont.truetype(font_path, 64),
                                  fill=(255, 255, 255, 255), anchor="rm")
        logo.save(out / f"logo-{idx}.png")


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
