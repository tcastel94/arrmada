"""Diagnostic des téléchargements bloqués : du message d'erreur à l'explication.

@author : Jeff Pomponne <jpomponne@gmail.com>

Sonarr, Radarr et SABnzbd disent ce qui ne va pas, mais en anglais technique
(« The download is stalled with no connections »). Ce fichier fait la
traduction, par du CODE et non par le modèle :

    message d'erreur connu  →  cause en français clair  +  action suggérée

Pourquoi ne pas laisser le modèle interpréter : un modèle de 9 milliards de
paramètres invente volontiers une explication plausible. Une table de règles
écrite une fois est exacte, relisible et testable. Le modèle reçoit la cause
dans le champ ``diagnosis`` et n'a plus qu'à la reformuler. Analogie : une
base de connaissances d'incidents (message connu → procédure), consultée
avant d'improviser.

Une erreur inconnue de la table ne reçoit PAS de diagnostic : le modèle voit
alors le message brut et doit le citer tel quel plutôt que deviner.

Ce fichier ne fait aucun appel réseau et ne modifie rien : il trie et annote
des données déjà lues. Il est partagé par les vrais outils (``tools.py``) et
par le faux monde du banc de test, pour que les deux se comportent pareil.

Les « suggestions » sont des phrases pour l'utilisateur. Aucune n'est exécutée
ici, et la boucle refuse toute action lancée pendant un diagnostic
(``agent.NO_ACTION_DURING_DIAGNOSTIC``).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

# ══════════════════════════════════════════════════════════════
# Reconnaître un titre dans un nom de release
# ══════════════════════════════════════════════════════════════


def fold(text: Any) -> str:
    """Minuscules sans accents."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def tokens(text: Any) -> list[str]:
    """Mots d'un titre ou d'un nom de release : « Dune.Part.Two.2024 » → dune, part, two, 2024."""
    return re.findall(r"[a-z0-9]+", fold(text))


def matches(name: Any, title: str, alternates: Iterable[str] = ()) -> bool:
    """Le nom contient-il tous les mots du titre, ou ceux d'un de ses titres exacts ?

    Comparaison par mots ENTIERS : « 2 » ne correspond pas à « 2024 ».
    ``alternates`` : titres exacts retrouvés dans la bibliothèque pour une
    demande approximative (« Dune 2 » → « Dune: Part Two »).
    """
    have = set(tokens(name))
    for candidate in (title, *alternates):
        wanted = tokens(candidate)
        if wanted and all(word in have for word in wanted):
            return True
    return False


# ══════════════════════════════════════════════════════════════
# La table : message connu → cause et suggestion
# ══════════════════════════════════════════════════════════════

_NEW_SEARCH = (
    "Lancer une nouvelle recherche pour récupérer une autre release (tu peux me le demander)."
)
_REMOVE_BY_HAND = (
    "Retirer cet élément de la file à la main dans Sonarr / Radarr, en cochant la liste noire : "
    "je ne supprime rien moi-même."
)

# (motif cherché dans le message, sans accents ni majuscules ; cause ; suggestion)
# L'ordre compte : le premier motif trouvé l'emporte, du plus précis au plus général.
RULES: tuple[tuple[str, str, str], ...] = (
    (
        r"\.(exe|scr|lnk|bat|msi)\b|executable|dangerous|malware|virus",
        "La release contient un fichier exécutable au lieu d'une vidéo : c'est un faux, "
        "probablement piégé.",
        f"Ne pas ouvrir ce fichier. {_REMOVE_BY_HAND} Puis lancer une nouvelle recherche.",
    ),
    (
        r"not enough free space|no space left|insufficient (disk )?space|disk (is )?full"
        r"|espace (disque )?insuffisant|disque plein",
        "Le téléchargement est terminé, mais il n'y a plus assez de place sur le disque de la "
        "médiathèque pour l'importer.",
        "Libérer de la place sur ce disque : l'import reprendra tout seul.",
    ),
    (
        r"stalled|no connections|no seeds|no peers|aucune (connexion|source)",
        "Torrent sans source : personne ne le partage en ce moment, il ne peut pas avancer.",
        _NEW_SEARCH,
    ),
    (
        # SABnzbd parle la langue de son interface : les messages français aussi.
        r"cannot be completed|not-complete|missing articles|articles? (are )?missing|aborted"
        r"|ne peut (pas )?etre termine|interrompu|articles? manquants?"
        r"|pas assez de blocs|not enough repair blocks",
        "Release Usenet incomplète : des morceaux manquent sur les serveurs (release ancienne "
        "ou retirée).",
        _NEW_SEARCH,
    ),
    (
        r"password|passworded|encrypted|mot de passe|chiffre",
        "L'archive est protégée par un mot de passe : release inutilisable, souvent un faux.",
        _NEW_SEARCH,
    ),
    (
        r"crc|unpack|par2|repair failed|corrupt|echec de la (reparation|decompression)|corrompu",
        "L'archive est corrompue : la décompression a échoué.",
        _NEW_SEARCH,
    ),
    (
        r"not an upgrade|not a (quality )?revision upgrade|existing file",
        "Le téléchargement est terminé, mais le fichier déjà présent dans la médiathèque est "
        "de qualité égale ou meilleure : l'import est refusé volontairement.",
        f"Rien à réparer. {_REMOVE_BY_HAND}",
    ),
    (
        r"no files found are eligible|no video files|no files found|sample",
        "Le téléchargement est terminé, mais il ne contient aucun fichier vidéo exploitable.",
        f"{_REMOVE_BY_HAND} Puis lancer une nouvelle recherche.",
    ),
    (
        r"unable to parse|unknown (series|movie)|title mismatch|matched to (series|movie) by id"
        r"|was not found in the grabbed release|was unexpected|manual import",
        "Le téléchargement est terminé, mais Sonarr / Radarr n'arrive pas à le rattacher au "
        "bon titre (nom de release inhabituel).",
        "Faire un import manuel dans l'interface : Activité › File d'attente › Import manuel.",
    ),
    (
        r"remote path|path mapping|does not exist|not accessible|permission|access to the path",
        "Sonarr / Radarr ne voit pas le dossier du téléchargement : problème de chemin ou de "
        "droits entre conteneurs.",
        "Vérifier les montages Docker et le « Remote Path Mapping » du client de téléchargement.",
    ),
    (
        r"download client.*(unavailable|not available)|unable to connect|connection refused"
        r"|unable to communicate",
        "Le client de téléchargement ne répond pas.",
        "Vérifier que SABnzbd / qBittorrent tourne et qu'il est joignable.",
    ),
)

_COMPILED = tuple((re.compile(pattern), cause, hint) for pattern, cause, hint in RULES)


def explain(*messages: Any) -> dict[str, str] | None:
    """Cause et suggestion pour un message d'erreur connu, sinon ``None``."""
    text = fold(" ".join(str(m) for m in messages if m))
    if not text.strip():
        return None
    for pattern, cause, suggestion in _COMPILED:
        if pattern.search(text):
            return {"cause": cause, "suggestion": suggestion}
    return None


# ══════════════════════════════════════════════════════════════
# File d'attente
# ══════════════════════════════════════════════════════════════

# États où un téléchargement n'avance plus sans intervention.
_BLOCKED_STATES = {"importpending", "importblocked", "importfailed", "failedpending", "failed"}
_BLOCKED_STATUS = {"warning", "failed", "stalled"}

UNKNOWN_ERROR = (
    "Erreur non répertoriée : cite le message exact à l'utilisateur, entre guillemets, sans "
    "inventer d'explication."
)


def is_blocked(item: dict[str, Any]) -> bool:
    return bool(
        item.get("error")
        or str(item.get("tracked_state", "")).lower() in _BLOCKED_STATES
        or str(item.get("status", "")).lower() in _BLOCKED_STATUS
    )


def annotate(item: dict[str, Any]) -> dict[str, Any]:
    """Ajoute ``diagnosis`` à un élément bloqué de la file. Les autres sont rendus tels quels."""
    if not is_blocked(item):
        return item
    found = explain(item.get("error"), item.get("detail"))
    if found is None and (item.get("error") or item.get("detail")):
        found = {"cause": UNKNOWN_ERROR, "suggestion": ""}
    if found is None:
        found = {
            "cause": "Téléchargement terminé, import pas encore fait, sans message d'erreur.",
            "suggestion": "Attendre quelques minutes ; si rien ne bouge, faire un import manuel "
            "dans l'interface.",
        }
    return {**item, "diagnosis": {k: v for k, v in found.items() if v}}


def queue_view(
    items: list[dict[str, Any]],
    *,
    title: str = "",
    alternates: Iterable[str] = (),
    clients: list[dict[str, Any]] | None = None,
    library: list[dict[str, Any]] | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Ce que ``get_queue`` rend au modèle : bloqués d'abord, chacun avec son diagnostic.

    ``library`` : ce que la bibliothèque possède pour le titre demandé, quand la
    file n'en contient rien. Un titre déjà complet n'a rien à télécharger : on
    le dit tout de suite, avant que le modèle ne cherche une panne.
    """
    alternates = list(alternates)
    total = len(items)
    if title:
        items = [item for item in items if matches(item.get("title"), title, alternates)]
    blocked = [annotate(item) for item in items if is_blocked(item)]
    ordered = blocked + [item for item in items if not is_blocked(item)]
    result: dict[str, Any] = {
        "count": len(items),
        "blocked_count": len(blocked),
        "items": ordered[:limit],
    }
    if title and alternates:
        result["matched_title"] = alternates[0]
    notes = []
    if len(items) > limit:
        notes.append(f"{len(items) - limit} téléchargements de plus, non listés.")
    if title and not items:
        notes.append(
            f"Aucun téléchargement pour « {title} » dans la file ({total} autres en cours). "
            "Appelle get_history avec ce titre pour voir s'il a échoué."
        )
    if title and not items and library:
        result["library"] = library
        complete = next((entry for entry in library if entry.get("complete")), None)
        if complete:
            result["diagnosis"] = {
                "cause": f"{complete['title']} est déjà dans la bibliothèque, au complet : il "
                "n'y a rien à télécharger.",
                "suggestion": "Rien à faire. Pour une meilleure qualité, c'est le profil de "
                "qualité qui décide : je n'y touche pas.",
            }
            notes = []
    paused = [c.get("service") for c in clients or [] if c.get("paused")]
    if paused:
        result["diagnosis"] = {
            "cause": f"{', '.join(str(p) for p in paused)} est en PAUSE : tous les "
            "téléchargements Usenet attendent, sans erreur.",
            "suggestion": "Reprendre les téléchargements dans l'interface de SABnzbd.",
        }
    if notes:
        result["note"] = " ".join(notes)
    if clients:
        result["sabnzbd"] = clients
    return result


# ══════════════════════════════════════════════════════════════
# Historique et journaux
# ══════════════════════════════════════════════════════════════

FAILURE_EVENTS = {"downloadfailed", "downloadignored"}
NO_HISTORY_NOTE = "Aucun événement ne correspond dans l'historique récent."
# Un titre sans aucune trace dans l'historique n'a jamais été « attrapé » : la
# cause est en amont (recherche), donc du côté des indexeurs. On le dit au
# modèle plutôt que d'espérer qu'il fasse le lien tout seul.
NO_HISTORY_FOR_TITLE_NOTE = (
    "Aucun événement pour ce titre dans l'historique récent. Si tu n'as pas encore appelé "
    "get_queue, appelle-le maintenant : un téléchargement bloqué s'y trouve. Si la file ne "
    "contient pas ce titre non plus, appelle get_indexer_status : aucune release n'a été trouvée."
)


def history_view(
    events: list[dict[str, Any]],
    *,
    title: str = "",
    alternates: Iterable[str] = (),
    only_failures: bool = False,
    limit: int = 15,
    logs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Ce que ``get_history`` rend au modèle : événements du titre, échecs expliqués, journaux.

    Si le titre n'a AUCUN événement, l'appelant joint l'état des indexeurs avec
    ``attach_indexers`` : l'étape suivante de l'enquête est faite par le code.
    """
    alternates = list(alternates)
    if title:
        events = [
            e
            for e in events
            if matches(f"{e.get('title', '')} {e.get('release', '')}", title, alternates)
        ]
    if only_failures:
        events = [e for e in events if str(e.get("event", "")).lower() in FAILURE_EVENTS]
    events = sorted(events, key=lambda e: e.get("date", ""), reverse=True)

    failures = [e for e in events if str(e.get("event", "")).lower() in FAILURE_EVENTS]
    result: dict[str, Any] = {"count": len(events), "events": events[:limit]}
    if title and alternates:
        result["matched_title"] = alternates[0]
    if failures:
        found = explain(*(e.get("reason") for e in failures))
        if found is None and any(e.get("reason") for e in failures):
            found = {"cause": UNKNOWN_ERROR}
        if found:
            result["diagnosis"] = {
                "failures": len(failures),
                **{k: v for k, v in found.items() if v},
            }
    if logs:
        result["logs"] = logs
    if not events:
        result["note"] = NO_HISTORY_FOR_TITLE_NOTE if title else NO_HISTORY_NOTE
    return result


def attach_indexers(history: dict[str, Any], indexers: dict[str, Any]) -> dict[str, Any]:
    """Historique vide pour un titre : on y joint le verdict des indexeurs.

    Rien dans l'historique = aucune release n'a été récupérée ; la question
    suivante est toujours « les indexeurs répondent-ils ? ». Vu au banc : le
    modèle s'arrêtait parfois ici en disant « cause non établie ». Le code
    pose donc la question lui-même.
    """
    if history.get("count") or "error" in indexers:
        return history
    summary = {key: indexers.get(key) for key in ("count", "working", "in_trouble")}
    history["indexers"] = summary
    if indexers.get("diagnosis"):
        history["diagnosis"] = indexers["diagnosis"]
        history["note"] = (
            "Aucune release récupérée pour ce titre, et les indexeurs sont en difficulté : "
            "c'est la cause la plus probable (voir « diagnosis »)."
        )
    else:
        history["note"] = (
            "Aucune release récupérée pour ce titre alors que les indexeurs fonctionnent : "
            "soit rien n'est encore disponible, soit aucune release ne passe le profil de "
            "qualité. Si tu n'as pas encore appelé get_queue, appelle-le."
        )
    return history


def log_lines(
    records: list[dict[str, Any]], title: str, alternates: Iterable[str] = (), limit: int = 5
) -> list[dict[str, Any]]:
    """Lignes d'avertissement ou d'erreur des journaux d'un *arr qui parlent du titre."""
    alternates = list(alternates)
    kept = []
    for record in records:
        message = str(record.get("message") or "")
        if not matches(message, title, alternates):
            continue
        line = {
            "time": str(record.get("time") or "")[:16],
            "level": record.get("level"),
            "message": message[:240],
        }
        found = explain(message, record.get("exception"))
        if found:
            line["cause"] = found["cause"]
        kept.append(line)
        if len(kept) >= limit:
            break
    return kept


# ══════════════════════════════════════════════════════════════
# Indexeurs
# ══════════════════════════════════════════════════════════════


def indexer_view(rows: list[dict[str, Any]], limit: int = 40) -> dict[str, Any]:
    """Ce que ``get_indexer_status`` rend : la liste, et le verdict quand trop sont en panne."""
    in_trouble = [
        r["name"]
        for r in rows
        if not r.get("enabled", True) or r.get("disabled_until") or r.get("messages")
    ]
    working = len(rows) - len(in_trouble)
    result: dict[str, Any] = {
        "count": len(rows),
        "working": working,
        "in_trouble": in_trouble,
        "indexers": rows[:limit],
    }
    if rows and working == 0:
        result["diagnosis"] = {
            "cause": "Aucun indexeur ne fonctionne : aucune release ne peut être trouvée.",
            "suggestion": "Vérifier les indexeurs dans Prowlarr (clé d'API, quota, site en panne).",
        }
    elif rows and working * 2 < len(rows):
        result["diagnosis"] = {
            "cause": f"Seulement {working} indexeur(s) sur {len(rows)} fonctionnent : les "
            "recherches trouvent beaucoup moins de releases, voire aucune.",
            "suggestion": "Vérifier les indexeurs en échec dans Prowlarr ; ils se réactivent "
            "parfois seuls à l'heure indiquée par « disabled_until ».",
        }
    return result
