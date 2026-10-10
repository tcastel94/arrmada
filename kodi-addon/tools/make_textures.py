#!/usr/bin/env python3
"""Génère les textures PNG des écrans sur mesure de l'add-on Kodi ArrMada.

Pourquoi un script plutôt que des images dessinées à la main ?
  Kodi ne sait pas dessiner de coins arrondis, de halo ou de dégradé : tout
  passe par des images. Les générer par script garantit des bords nets
  (anticrénelage calculé), des tailles cohérentes avec le XML, et permet de
  les refaire à l'identique. Aucune dépendance : uniquement la bibliothèque
  standard Python (zlib + struct pour écrire le PNG).

Les textures sont BLANCHES : la couleur est appliquée dans le XML avec
`colordiffuse="AARRGGBB"` (ex. accent #4A9EFF → FF4A9EFF). Une seule image
sert donc pour toutes les couleurs.

Les images « 9-slice » (coins préservés, centre étiré) s'utilisent avec
l'attribut `border` indiqué dans le tableau TEXTURES ci-dessous.

Usage : python3 kodi-addon/tools/make_textures.py
Sortie : kodi-addon/script.arrmada/resources/skins/Default/media/arrmada/
"""

from __future__ import annotations

import math
import struct
import zlib
from collections.abc import Callable
from pathlib import Path

OUT_DIR = (
    Path(__file__).resolve().parent.parent
    / "script.arrmada"
    / "resources"
    / "skins"
    / "Default"
    / "media"
    / "arrmada"
)

# Une fonction « alpha » reçoit les coordonnées du CENTRE d'un pixel et
# renvoie une opacité entre 0.0 et 1.0. Les pixels sont toujours blancs.
AlphaFn = Callable[[float, float], float]


# ─────────────────────────────────────────────────────────────────────────────
# Écriture PNG (RGBA 8 bits) sans Pillow
# ─────────────────────────────────────────────────────────────────────────────


def _chunk(kind: bytes, data: bytes) -> bytes:
    """Bloc PNG : longueur + type + données + CRC32."""
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_png(path: Path, width: int, height: int, alpha: AlphaFn) -> None:
    """Écrit un PNG blanc dont l'opacité de chaque pixel vient de `alpha`."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filtre PNG « None » pour chaque ligne
        for x in range(width):
            a = max(0.0, min(1.0, alpha(x + 0.5, y + 0.5)))
            rows += bytes((255, 255, 255, round(a * 255)))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)


# ─────────────────────────────────────────────────────────────────────────────
# Formes (fonctions de distance signée : < 0 dedans, > 0 dehors, en pixels)
# ─────────────────────────────────────────────────────────────────────────────


def sd_round_rect(
    px: float, py: float, cx: float, cy: float, hw: float, hh: float, r: float
) -> float:
    """Distance signée à un rectangle arrondi (centre cx,cy ; demi-tailles hw,hh)."""
    qx = abs(px - cx) - (hw - r)
    qy = abs(py - cy) - (hh - r)
    outside = math.hypot(max(qx, 0.0), max(qy, 0.0))
    inside = min(max(qx, qy), 0.0)
    return outside + inside - r


def coverage(d: float) -> float:
    """Anticrénelage : part du pixel couverte par la forme (bord sur 1 px)."""
    return max(0.0, min(1.0, 0.5 - d))


def round_rect(w: int, h: int, r: float) -> AlphaFn:
    """Rectangle arrondi plein, occupant toute l'image."""
    return lambda x, y: coverage(sd_round_rect(x, y, w / 2, h / 2, w / 2, h / 2, r))


def ring(w: int, h: int, r: float, thickness: float) -> AlphaFn:
    """Contour arrondi (anneau de focus) d'épaisseur `thickness`."""

    def fn(x: float, y: float) -> float:
        d = sd_round_rect(x, y, w / 2, h / 2, w / 2, h / 2, r)
        return min(coverage(d), coverage(-(d + thickness)))

    return fn


def glow(size: int, inset: float, r: float, sigma: float) -> AlphaFn:
    """Halo : rectangle arrondi plein, bord estompé façon flou gaussien."""

    def fn(x: float, y: float) -> float:
        half = size / 2 - inset
        d = sd_round_rect(x, y, size / 2, size / 2, half, half, r)
        return 1.0 if d <= 0 else math.exp(-(d * d) / (2 * sigma * sigma))

    return fn


def blob(size: int) -> AlphaFn:
    """Tache lumineuse ronde (fond « aurore »), opacité gaussienne."""

    def fn(x: float, y: float) -> float:
        d = math.hypot(x - size / 2, y - size / 2) / (size / 2)
        return math.exp(-(d * d) * 4.0) * (1.0 if d < 1 else 0.0)

    return fn


def disc(size: int) -> AlphaFn:
    """Disque plein (pastille d'état)."""
    return lambda x, y: coverage(math.hypot(x - size / 2, y - size / 2) - size / 2)


def spinner(size: int, thickness: float) -> AlphaFn:
    """Arc de chargement : anneau dont l'opacité croît avec l'angle (« comète »)."""

    def fn(x: float, y: float) -> float:
        dx, dy = x - size / 2, y - size / 2
        r_out = size / 2 - 1
        dist = math.hypot(dx, dy)
        band = min(coverage(dist - r_out), coverage(r_out - thickness - dist))
        angle = (math.atan2(dy, dx) + math.pi) / (2 * math.pi)  # 0 → 1
        return band * (0.08 + 0.92 * angle**2)

    return fn


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def grad_h(w: int) -> AlphaFn:
    """Dégradé horizontal : opaque à gauche → transparent à droite."""
    return lambda x, _y: 1.0 - smoothstep(x / w)


def grad_v(h: int) -> AlphaFn:
    """Dégradé vertical : transparent en haut → opaque en bas."""
    return lambda _x, y: smoothstep(y / h)


# ─────────────────────────────────────────────────────────────────────────────
# Catalogue : nom → (largeur, hauteur, forme, usage / border à mettre en XML)
# ─────────────────────────────────────────────────────────────────────────────

POSTER_W, POSTER_H = 220, 330  # taille des affiches dans le XML (ratio 2:3)

TEXTURES: dict[str, tuple[int, int, AlphaFn, str]] = {
    "white.png": (8, 8, lambda _x, _y: 1.0, "aplat de couleur (fonds)"),
    "rounded-12.png": (64, 64, round_rect(64, 64, 12), 'border="14" — boutons, pastilles'),
    "rounded-24.png": (96, 96, round_rect(96, 96, 24), 'border="26" — cartes'),
    "ring-24.png": (96, 96, ring(96, 96, 24, 2), 'border="26" — liseré de carte 2 px'),
    "glow.png": (128, 128, glow(128, 40, 14, 14), 'border="56" — halo de focus / ombre'),
    "bar.png": (32, 12, round_rect(32, 12, 6), 'border="6,0,6,0" — barres de progression'),
    "circle.png": (32, 32, disc(32), "pastille d'état"),
    "blob.png": (256, 256, blob(256), "lumière d'ambiance (étirée, sans border)"),
    "spinner.png": (96, 96, spinner(96, 7), "chargement (animation rotate)"),
    "grad-h.png": (256, 4, grad_h(256), "voile gauche → droite sur le fanart"),
    "grad-v.png": (4, 256, grad_v(256), "voile haut → bas sur le fanart"),
    "poster-mask.png": (
        POSTER_W,
        POSTER_H,
        round_rect(POSTER_W, POSTER_H, 14),
        "masque `diffuse` des affiches (coins arrondis)",
    ),
    "poster-ring.png": (
        POSTER_W,
        POSTER_H,
        ring(POSTER_W, POSTER_H, 14, 4),
        "anneau de focus des affiches (mêmes coins que le masque)",
    ),
}


def main(out_dir: Path = OUT_DIR) -> None:
    """Écrit toutes les textures dans `out_dir` (les tests l'appellent sur un
    dossier temporaire pour vérifier que les PNG du dépôt sont à jour)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (w, h, fn, usage) in TEXTURES.items():
        write_png(out_dir / name, w, h, fn)
        print(f"  + {name:18} {w:>3}×{h:<3}  {usage}")
    print(f"OK : {len(TEXTURES)} textures dans {out_dir}")


if __name__ == "__main__":
    main()
