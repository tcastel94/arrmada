#!/usr/bin/env python3
"""Exporte toutes les images de la marque ArrMada depuis branding/arrmada-mark.svg.

Pourquoi un script ?
  Le logo n'existe qu'en un seul endroit (le SVG). Le favicon, les icônes de
  la web app, l'image de partage et l'icône et le fond de l'add-on Kodi en
  sont DÉRIVÉS : pour changer le logo, on modifie le SVG puis on relance ce
  script. Aucune image n'est retouchée à la main.

Prérequis (Ubuntu/Debian) : sudo apt install librsvg2-bin python3-pil
Usage : python3 branding/export.py

Fichiers produits (à committer) :
  branding/arrmada-icon.svg, branding/arrmada-icon-square.svg
  frontend/src/app/{icon.png, apple-icon.png, favicon.ico}
  frontend/public/{logo-mark.png, logo-mark-192.png, logo-full.png, og-image.png}
  docs/banner.png (bannière du README)
  kodi-addon/script.arrmada/resources/{icon.png, fanart.jpg}
  kodi-addon/script.arrmada/resources/skins/Default/media/arrmada/brand-*.png
    (calques de l'intro Kodi : jambes du A, lecture, nom, accroche)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BRANDING = ROOT / "branding"
MARK_SVG = BRANDING / "arrmada-mark.svg"
FONT = ROOT / "frontend" / "src" / "app" / "fonts" / "GeistVF.woff"
FRONT_APP = ROOT / "frontend" / "src" / "app"
FRONT_PUBLIC = ROOT / "frontend" / "public"
KODI_RES = ROOT / "kodi-addon" / "script.arrmada" / "resources"
KODI_MEDIA = KODI_RES / "skins" / "Default" / "media" / "arrmada"

BG = (10, 14, 22)  # #0A0E16, fond de la web app et de l'appli Kodi
ACCENT = (74, 158, 255)  # #4A9EFF
CYAN = (34, 224, 238)  # #22E0EE
TEXT = (245, 247, 250)
MUTED = (139, 151, 171)


# ─────────────────────────────────────────────────────────────────────────────
# Icône (SVG) : tuile sombre + logo, déclinée arrondie ou carrée
# ─────────────────────────────────────────────────────────────────────────────


def mark_inner() -> str:
    """Contenu du SVG du logo (dégradé + tracés), sans la balise <svg> ni commentaire."""
    svg = MARK_SVG.read_text(encoding="utf-8")
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    return re.sub(r"<!--.*?-->", "", inner, flags=re.S).strip()


def icon_svg(radius: int) -> str:
    """Tuile 512×512 : fond dégradé, liseré, halo bleu, logo à 62 % de la taille.

    radius=112 : coins arrondis (favicon, web app) ; radius=0 : carré plein,
    pour iOS (qui arrondit lui-même) et Kodi (icônes sans transparence).
    """
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <!-- Généré par branding/export.py depuis arrmada-mark.svg : ne pas modifier à la main. -->
  <defs>
    <radialGradient id="tile-bg" cx="0.22" cy="0" r="1.25">
      <stop offset="0" stop-color="#17223A"/>
      <stop offset="0.6" stop-color="#0B111D"/>
      <stop offset="1" stop-color="#080B12"/>
    </radialGradient>
    <radialGradient id="tile-glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#4A9EFF" stop-opacity="0.32"/>
      <stop offset="1" stop-color="#4A9EFF" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="{radius}" fill="url(#tile-bg)"/>
  <circle cx="256" cy="246" r="210" fill="url(#tile-glow)"/>
  <rect x="2" y="2" width="508" height="508" rx="{max(radius - 2, 0)}" fill="none" stroke="#FFFFFF" stroke-opacity="0.08" stroke-width="4"/>
  <g transform="translate(96 96) scale(5)">
    {mark_inner()}
  </g>
</svg>
"""


def rasterize(svg_path: Path, out: Path, width: int, height: int | None = None) -> None:
    """SVG → PNG via rsvg-convert (librsvg), net à toutes les tailles."""
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["rsvg-convert", "-w", str(width), "-h", str(height or width), "-o", str(out), str(svg_path)],
        check=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Compositions (image de partage, fond Kodi, logo complet)
# ─────────────────────────────────────────────────────────────────────────────


def font(size: int, weight: int) -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT), size)
    face.set_variation_by_axes([weight])  # Geist est une police variable
    return face


def aurora(size: tuple[int, int]) -> Image.Image:
    """Fond nuit + deux lumières floues (bleu en haut à droite, cyan en bas à gauche)."""
    w, h = size
    img = Image.new("RGB", size, BG)
    light = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(light)
    draw.ellipse((int(w * 0.55), int(-h * 0.55), int(w * 1.25), int(h * 0.55)), fill=(36, 78, 140))
    draw.ellipse((int(-w * 0.25), int(h * 0.55), int(w * 0.35), int(h * 1.4)), fill=(10, 80, 92))
    light = light.filter(ImageFilter.GaussianBlur(min(w, h) // 5))
    return ImageChops.screen(img, light)  # « éclaircir » : la lumière s'ajoute au fond


def gradient_text(img: Image.Image, xy: tuple[int, int], text: str, face) -> int:
    """Texte rempli du dégradé de marque ; renvoie sa largeur (avance)."""
    left, top, right, bottom = face.getbbox(text)
    mask = Image.new("L", (right, bottom), 0)
    ImageDraw.Draw(mask).text((0, 0), text, font=face, fill=255)
    grad = Image.new("RGB", mask.size)
    gdraw = ImageDraw.Draw(grad)
    for x in range(mask.size[0]):
        t = x / max(1, mask.size[0] - 1)
        gdraw.line([(x, 0), (x, mask.size[1])], fill=tuple(int(a + (b - a) * t) for a, b in zip(ACCENT, CYAN)))
    img.paste(grad, xy, mask)
    return int(face.getlength(text))


def spaced_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, face, fill, spacing: float) -> None:
    """Petites capitales espacées (« COMMAND CENTER »), lettre par lettre."""
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=face, fill=fill)
        x += face.getlength(char) + spacing


def lockup(img: Image.Image, icon_png: Path, x: int, y: int, icon_size: int, title_size: int, tagline: str) -> None:
    """Icône + « ArrMada » (Arr en dégradé) + accroche, alignés horizontalement."""
    icon = Image.open(icon_png).convert("RGBA").resize((icon_size, icon_size), Image.LANCZOS)
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (x - 10, y - 10, x + icon_size + 10, y + icon_size + 10), radius=icon_size // 4, fill=(*ACCENT, 120)
    )
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(icon_size // 6)))
    img.alpha_composite(icon, (x, y))

    title = font(title_size, 760)
    tx = x + icon_size + int(icon_size * 0.24)
    ty = y + int(icon_size * 0.5) - int(title_size * 0.78)
    advance = gradient_text(img, (tx, ty), "Arr", title)
    draw = ImageDraw.Draw(img)
    draw.text((tx + advance, ty), "Mada", font=title, fill=TEXT)
    spaced_text(draw, (tx + 4, ty + int(title_size * 1.12)), tagline, font(int(title_size * 0.2), 600), MUTED, title_size * 0.055)


def compose(size: tuple[int, int], icon_png: Path, icon_size: int, title_size: int) -> Image.Image:
    img = aurora(size).convert("RGBA")
    total = icon_size + int(icon_size * 0.24) + int(font(title_size, 760).getlength("ArrMada"))
    x = (size[0] - total) // 2
    y = (size[1] - icon_size) // 2 - int(size[1] * 0.02)
    lockup(img, icon_png, x, y, icon_size, title_size, "COMMAND CENTER")
    return img.convert("RGB")


# ─────────────────────────────────────────────────────────────────────────────
# Calques de l'intro Kodi : le logo découpé en pièces animées séparément
# ─────────────────────────────────────────────────────────────────────────────


def mark_paths() -> tuple[str, str]:
    """Tracés (d=…) du « A » et du bouton lecture, lus dans le SVG source."""
    paths = re.findall(r'<path d="([^"]+)"', MARK_SVG.read_text(encoding="utf-8"))
    return paths[0], paths[1]


def layer_svg(body: str) -> str:
    """Calque 64×64 transparent. Dégradé en coordonnées absolues (userSpaceOnUse)
    calé sur la boîte du « A » : chaque jambe garde la couleur qu'elle a dans
    le logo complet."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="64" height="64">
  <defs>
    <linearGradient id="g" gradientUnits="userSpaceOnUse" x1="11" y1="9" x2="53" y2="54">
      <stop offset="0" stop-color="#4A9EFF"/>
      <stop offset="1" stop-color="#22E0EE"/>
    </linearGradient>
  </defs>
  {body}
</svg>
"""


def kodi_intro_layers(tmp: Path) -> list[Path]:
    a_path, play_path = mark_paths()
    # « M11 54 L32 9 L53 54 » → jambe gauche « M11 54 L32 9 », droite « M32 9 L53 54 »
    points = re.findall(r"[ML]\s*([\d.]+)\s+([\d.]+)", a_path)
    (x1, y1), (x2, y2), (x3, y3) = points
    stroke = 'fill="none" stroke="url(#g)" stroke-width="9" stroke-linecap="round"'
    layers = {
        "brand-leg-left.png": f'<path d="M{x1} {y1} L{x2} {y2}" {stroke}/>',
        "brand-leg-right.png": f'<path d="M{x2} {y2} L{x3} {y3}" {stroke}/>',
        "brand-play.png": f'<path d="{play_path}" fill="#EAF6FF"/>',
    }
    written = []
    for name, body in layers.items():
        svg = tmp / f"{name}.svg"
        svg.write_text(layer_svg(body), encoding="utf-8")
        rasterize(svg, KODI_MEDIA / name, 512)
        written.append(KODI_MEDIA / name)

    # Nom « ArrMada » (police de la web app, Geist) et accroche, fonds transparents
    title = font(150, 760)
    word = Image.new("RGBA", (int(title.getlength("ArrMada")) + 20, 190), (0, 0, 0, 0))
    advance = gradient_text(word, (6, 0), "Arr", title)
    ImageDraw.Draw(word).text((6 + advance, 0), "Mada", font=title, fill=TEXT)
    word = word.crop(word.getbbox())
    word.save(KODI_MEDIA / "brand-wordmark.png", optimize=True)

    tag_font = font(30, 600)
    tag = Image.new("RGBA", (620, 50), (0, 0, 0, 0))
    spaced_text(ImageDraw.Draw(tag), (4, 4), "COMMAND CENTER", tag_font, MUTED, 9)
    tag = tag.crop(tag.getbbox())
    tag.save(KODI_MEDIA / "brand-tagline.png", optimize=True)
    return [*written, KODI_MEDIA / "brand-wordmark.png", KODI_MEDIA / "brand-tagline.png"]


# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert introuvable : sudo apt install librsvg2-bin")

    rounded, square = BRANDING / "arrmada-icon.svg", BRANDING / "arrmada-icon-square.svg"
    rounded.write_text(icon_svg(112), encoding="utf-8")
    square.write_text(icon_svg(0), encoding="utf-8")

    with tempfile.TemporaryDirectory() as tmp:
        big = Path(tmp) / "icon-1024.png"
        rasterize(rounded, big, 1024)

        # Web app (conventions Next.js App Router + fichiers publics)
        rasterize(rounded, FRONT_APP / "icon.png", 512)
        rasterize(square, FRONT_APP / "apple-icon.png", 180)
        rasterize(rounded, FRONT_PUBLIC / "logo-mark.png", 512)
        rasterize(rounded, FRONT_PUBLIC / "logo-mark-192.png", 192)
        ico_src = Path(tmp) / "icon-256.png"
        rasterize(rounded, ico_src, 256)
        Image.open(ico_src).save(FRONT_APP / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
        compose((1200, 630), big, 190, 112).save(FRONT_PUBLIC / "og-image.png", optimize=True)
        compose((1000, 400), big, 150, 92).save(FRONT_PUBLIC / "logo-full.png", optimize=True)
        compose((1600, 480), big, 190, 116).save(ROOT / "docs" / "banner.png", optimize=True)

        # Add-on Kodi : icône carrée sans transparence + fond 1920×1080
        icon = Path(tmp) / "kodi-icon.png"
        rasterize(square, icon, 512)
        Image.open(icon).convert("RGB").save(KODI_RES / "icon.png", optimize=True)
        compose((1920, 1080), big, 280, 168).save(KODI_RES / "fanart.jpg", quality=90, optimize=True)
        intro = kodi_intro_layers(Path(tmp))

    for path in (
        rounded,
        square,
        FRONT_APP / "icon.png",
        FRONT_APP / "apple-icon.png",
        FRONT_APP / "favicon.ico",
        FRONT_PUBLIC / "logo-mark.png",
        FRONT_PUBLIC / "logo-mark-192.png",
        FRONT_PUBLIC / "logo-full.png",
        FRONT_PUBLIC / "og-image.png",
        ROOT / "docs" / "banner.png",
        KODI_RES / "icon.png",
        KODI_RES / "fanart.jpg",
        *intro,
    ):
        print(f"  + {path.relative_to(ROOT)}")
    print("OK : images de la marque régénérées")


if __name__ == "__main__":
    main()
