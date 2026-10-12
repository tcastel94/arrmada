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


def circle_ring(size: int, thickness: float) -> AlphaFn:
    """Cercle fin (onde qui s'élargit pendant l'intro)."""

    def fn(x: float, y: float) -> float:
        dist = math.hypot(x - size / 2, y - size / 2)
        r_out = size / 2 - 1
        return min(coverage(dist - r_out), coverage(r_out - thickness - dist))

    return fn


def sweep(w: int, h: int) -> AlphaFn:
    """Reflet : ovale de lumière, opaque au centre et fondu sur tous les bords."""
    return lambda x, y: smoothstep(1 - abs(x / w * 2 - 1)) * smoothstep(1 - abs(y / h * 2 - 1))


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
# Disque Blu-ray / DVD de la fiche (sort du boîtier et tourne)
# ─────────────────────────────────────────────────────────────────────────────
# Proportions d'un vrai disque de 120 mm, en fraction du rayon R :
#   trou central 15 mm (0,125 R), moyeu transparent jusqu'à ~46 mm (0,38 R),
#   anneau d'empilage vers 0,28 R, zone imprimée de 0,38 R au bord.
DISC = 512
DISC_HOLE, DISC_PRINT = 0.125, 0.38


def _disc_radius(x: float, y: float) -> tuple[float, float]:
    """(distance au centre en px, rayon R en px) pour une texture DISC × DISC."""
    return math.hypot(x - DISC / 2, y - DISC / 2), DISC / 2 - 1


def disc_print_mask() -> AlphaFn:
    """Masque `diffuse` du disque dessiné, au format de l'AFFICHE (2:3).

    Kodi applique le masque à l'image entière, AVANT tout recadrage
    (aspectratio « scale ») : sur une affiche recadrée en carré, un masque
    carré devient une ellipse coupée (disque aux bords plats). On garde donc
    l'affiche entière (contrôle 2:3, sans recadrage) et le masque est 2:3 :
    un cercle de la largeur de l'image, centré, zone imprimée seulement."""

    def fn(x: float, y: float) -> float:
        d = math.hypot(x - DISC / 2, y - DISC * 3 / 4)
        r = DISC / 2 - 1
        return min(coverage(d - r), coverage(DISC_PRINT * r - d))

    return fn


def disc_hub() -> AlphaFn:
    """Moyeu en plastique transparent : voile léger, anneau d'empilage, bord du trou."""

    def fn(x: float, y: float) -> float:
        d, r = _disc_radius(x, y)
        hub = min(coverage(d - DISC_PRINT * r), coverage(DISC_HOLE * r - d))
        stack = min(coverage(d - 0.29 * r), coverage(0.27 * r - d))
        hole_edge = min(coverage(d - 0.145 * r), coverage(DISC_HOLE * r - d))
        return hub * max(0.30, 0.75 * stack, 0.85 * hole_edge)

    return fn


def disc_edge() -> AlphaFn:
    """Tranche du disque (liseré extérieur) + bord de la zone imprimée."""

    def fn(x: float, y: float) -> float:
        d, r = _disc_radius(x, y)
        rim = min(coverage(d - r), coverage(0.975 * r - d))
        print_edge = min(coverage(d - (DISC_PRINT + 0.008) * r), coverage(DISC_PRINT * r - d))
        return max(0.55 * rim, 0.35 * print_edge)

    return fn


def disc_shine() -> AlphaFn:
    """Reflet de lumière FIXE (la lampe ne tourne pas avec le disque) : deux
    pinceaux opposés à 45° et 225°, plus un voile très léger."""

    def fn(x: float, y: float) -> float:
        d, r = _disc_radius(x, y)
        inside = min(coverage(d - r), coverage(DISC_HOLE * r - d))
        if inside <= 0:
            return 0.0
        angle = math.degrees(math.atan2(y - DISC / 2, x - DISC / 2)) % 180  # deux pinceaux
        beam = math.exp(-(((angle - 45) / 16) ** 2))
        return inside * (0.05 + 0.33 * beam * (0.35 + 0.65 * d / r))

    return fn


def disc_shadow() -> AlphaFn:
    """Ombre douce sous le disque sorti (disque flou)."""

    def fn(x: float, y: float) -> float:
        d = math.hypot(x - DISC / 2, y - DISC / 2) / (DISC / 2)
        return 1.0 - smoothstep((d - 0.72) / 0.28)

    return fn


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
    "ring-circle.png": (256, 256, circle_ring(256, 5), "onde de l'intro (zoom + fondu)"),
    "sweep.png": (64, 128, sweep(64, 128), "reflet qui traverse le logo pendant l'intro"),
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
    # Fiche : boîtier Blu-ray / 4K / DVD et son disque
    "case-insert-mask.png": (
        360,
        540,
        round_rect(360, 540, 6),
        "masque `diffuse` de la jaquette dans le boîtier (coins à peine arrondis)",
    ),
    "disc-mask.png": (
        DISC,
        DISC * 3 // 2,
        disc_print_mask(),
        "masque `diffuse` du disque dessiné (format affiche 2:3)",
    ),
    "disc-hub.png": (DISC, DISC, disc_hub(), "moyeu transparent du disque"),
    "disc-edge.png": (DISC, DISC, disc_edge(), "tranche du disque"),
    "disc-shine.png": (DISC, DISC, disc_shine(), "reflet fixe sur le disque qui tourne"),
    "disc-shadow.png": (256, 256, lambda x, y: disc_shadow()(x * 2, y * 2), "ombre du disque"),
}


# Barres de progression des LISTES (téléchargements, saisons, volume).
# Kodi ne sait pas remplir une barre « progress » à partir d'une propriété
# d'élément de liste : chaque ligne affiche donc l'image pré-rendue au bon
# pourcentage (bar-000.png … bar-100.png, par pas de 2 %). Couleurs intégrées :
# piste blanche à 12 %, remplissage en dégradé accent → cyan.
BAR_W, BAR_H, BAR_STEP = 1000, 12, 2
ACCENT, CYAN = (74, 158, 255), (34, 224, 238)


def write_bar(path: Path, pct: int) -> None:
    fill = BAR_W * pct / 100
    rows = bytearray()
    for y in range(BAR_H):
        rows.append(0)
        for x in range(BAR_W):
            cx, cy = x + 0.5, y + 0.5
            track = coverage(
                sd_round_rect(cx, cy, BAR_W / 2, BAR_H / 2, BAR_W / 2, BAR_H / 2, BAR_H / 2)
            )
            inside = (
                coverage(
                    sd_round_rect(
                        cx, cy, fill / 2, BAR_H / 2, fill / 2, BAR_H / 2, min(BAR_H / 2, fill / 2)
                    )
                )
                if fill > 0
                else 0.0
            )
            t = x / BAR_W
            color = tuple(round(a + (b - a) * t) for a, b in zip(ACCENT, CYAN))
            # Remplissage par-dessus la piste (alpha 0,12)
            alpha = inside + track * 0.12 * (1 - inside)
            if alpha <= 0:
                rows += bytes((255, 255, 255, 0))
                continue
            mix = inside / alpha
            rgb = tuple(round(c * mix + 255 * (1 - mix)) for c in color)
            rows += bytes((*rgb, round(alpha * 255)))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", BAR_W, BAR_H, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def main(out_dir: Path = OUT_DIR) -> None:
    """Écrit toutes les textures dans `out_dir` (les tests l'appellent sur un
    dossier temporaire pour vérifier que les PNG du dépôt sont à jour)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (w, h, fn, usage) in TEXTURES.items():
        write_png(out_dir / name, w, h, fn)
        print(f"  + {name:18} {w:>3}×{h:<3}  {usage}")
    bars = out_dir / "progress"
    bars.mkdir(exist_ok=True)
    for pct in range(0, 101, BAR_STEP):
        write_bar(bars / f"bar-{pct:03d}.png", pct)
    print(f"  + progress/bar-000…100.png  {BAR_W}×{BAR_H}  barres de progression des listes")
    print(f"OK : {len(TEXTURES)} textures + {100 // BAR_STEP + 1} barres dans {out_dir}")


if __name__ == "__main__":
    main()
