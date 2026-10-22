"""Décalage de sous-titres : avancer ou retarder tous les horaires d'un fichier.

Le lecteur de la TV (Media3) n'a pas de réglage « retard des sous-titres »
comme Kodi : c'est donc le serveur qui sert une copie décalée du fichier
(`?shift=1500` : +1,5 s, les phrases arrivent plus tard ; négatif : plus tôt),
comme un `sed` sur les horodatages. Le fichier sur le disque n'est jamais
modifié.

Formats : SRT (`00:01:02,345 --> …`), WebVTT (`00:01:02.345 --> …`, heures
facultatives) et ASS / SSA (lignes `Dialogue:` en `0:01:02.34`). Un horaire
qui deviendrait négatif est ramené à zéro.
"""

from __future__ import annotations

import re

MAX_SHIFT_MS = 600_000  # ±10 min : au-delà, ce n'est plus un décalage mais un autre fichier

# SRT / VTT : « 01:02:03,456 » ou « 01:02:03.456 » ou (VTT) « 02:03.456 »
_CUE_TIME = re.compile(r"(?:(\d{1,2}):)?(\d{2}):(\d{2})([,.])(\d{3})")
# ASS : « Dialogue: 0,0:01:02.34,0:01:05.67,… »
_ASS_LINE = re.compile(
    r"^(Dialogue:\s*[^,]*,)(\d+:\d{2}:\d{2}\.\d{2}),(\d+:\d{2}:\d{2}\.\d{2})(,.*)$"
)


def _fmt_cue(ms: int, sep: str, with_hours: bool) -> str:
    ms = max(0, ms)
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, milli = divmod(rest, 1000)
    clock = f"{m:02d}:{s:02d}{sep}{milli:03d}"
    return f"{h:02d}:{clock}" if with_hours or h else clock


def _shift_cue_line(line: str, shift_ms: int) -> str:
    def repl(m: re.Match[str]) -> str:
        hours = int(m.group(1) or 0)
        total = ((hours * 60 + int(m.group(2))) * 60 + int(m.group(3))) * 1000 + int(m.group(5))
        return _fmt_cue(total + shift_ms, m.group(4), m.group(1) is not None)

    return _CUE_TIME.sub(repl, line)


def _shift_ass_time(value: str, shift_ms: int) -> str:
    h, m, rest = value.split(":")
    s, cs = rest.split(".")
    total = max(0, ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(cs) * 10 + shift_ms)
    h2, rest2 = divmod(total, 3_600_000)
    m2, rest2 = divmod(rest2, 60_000)
    s2, milli = divmod(rest2, 1000)
    return f"{h2}:{m2:02d}:{s2:02d}.{milli // 10:02d}"


def shift(text: str, ext: str, shift_ms: int) -> str:
    """Copie du sous-titre [text] (format [ext]) décalée de [shift_ms] millisecondes."""
    if not shift_ms:
        return text
    if not -MAX_SHIFT_MS <= shift_ms <= MAX_SHIFT_MS:
        raise ValueError("Décalage hors bornes (±10 min)")
    lines = text.split("\n")
    if ext in ("ass", "ssa"):
        out = []
        for line in lines:
            m = _ASS_LINE.match(line.rstrip("\r"))
            if m:
                cr = "\r" if line.endswith("\r") else ""
                line = (
                    f"{m.group(1)}{_shift_ass_time(m.group(2), shift_ms)},"
                    f"{_shift_ass_time(m.group(3), shift_ms)}{m.group(4)}{cr}"
                )
            out.append(line)
        return "\n".join(out)
    # SRT / VTT : seules les lignes d'horaires (« --> ») bougent, jamais le texte
    return "\n".join(_shift_cue_line(line, shift_ms) if "-->" in line else line for line in lines)
