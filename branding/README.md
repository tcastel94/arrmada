# Marque ArrMada

Le logo **« Lecture »** est un « A » dont la barre est un bouton lecture : la médiathèque et la commande réunies en un seul signe.

| Élément | Valeur |
|---|---|
| Source unique | `arrmada-mark.svg` (logo seul, fond transparent) |
| Couleurs | dégradé `#4A9EFF` → `#22E0EE`, bouton lecture `#EAF6FF`, fond nuit `#0A0E16` |
| Police du nom | Geist (celle de la web app), graisse 760 : « **Arr** » en dégradé, « Mada » en blanc |
| Accroche | `COMMAND CENTER`, capitales espacées, gris `#8B97AB` |

## Régénérer les images

Toutes les images de la marque sont **dérivées** du SVG. Il ne faut jamais les retoucher à la main.

```bash
sudo apt install librsvg2-bin python3-pil   # une seule fois
python3 branding/export.py
```

Le script produit :
- `arrmada-icon.svg` et `arrmada-icon-square.svg` : la tuile d'application, arrondie ou carrée.
- Web app : `frontend/src/app/{icon.png, apple-icon.png, favicon.ico}`, `frontend/public/{logo-mark.png, logo-mark-192.png, logo-full.png, og-image.png}`.
- README : `docs/banner.png`.
- Add-on Kodi : `resources/icon.png` (carrée, sans transparence, comme le demande Kodi) et `resources/fanart.jpg`.
- Intro de l'appli Kodi : les calques `resources/skins/Default/media/arrmada/brand-*.png` (les deux jambes du « A », le bouton lecture, le nom et l'accroche).

Dans la web app, le logo est dessiné en SVG par le composant `frontend/src/components/brand/brand-mark.tsx`, qui reprend les mêmes tracés. Si le logo change, il faut modifier les deux fichiers.
