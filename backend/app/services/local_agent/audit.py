"""Journal d'audit de l'agent local : une ligne JSON par événement.

@author : Jeff Pomponne <jpomponne@gmail.com>

Fichier ``DATA_DIR/local_agent_audit.jsonl`` (sur l'hôte : ``./data/``). Chaque
demande, chaque appel d'outil (accepté ou rejeté), chaque résultat et chaque
réponse finale y laisse une ligne. Analogie : un ``auditd`` dédié à l'agent.

Pourquoi un fichier texte plutôt qu'une table en base : il se lit avec les
outils de tous les jours, sans passer par l'application ::

    tail -f data/local_agent_audit.jsonl | jq .
    jq 'select(.kind == "tool_call" and .valid == false)' data/local_agent_audit.jsonl

Types de lignes (champ ``kind``) :

- ``request``     : la demande de l'utilisateur ;
- ``tool_call``   : outil demandé par le modèle, ses arguments, ``valid`` ;
- ``tool_result`` : résultat rendu au modèle (tronqué), ``ok``, durée ;
- ``proposal``    : action préparée par un outil d'écriture (résumé, appel prévu) ;
- ``confirmation``: réponse de l'utilisateur (approuvée, refusée, expirée) ;
- ``action_result``: ce que l'exécution a donné (ou « dry_run » : rien exécuté) ;
- ``correction``  : le code a repris le modèle (confirmation demandée sans outil) ;
- ``answer``      : réponse finale ;
- ``error``       : tour interrompu, avec la raison.

Rotation simple : au-delà de 10 Mo, le fichier devient ``.1`` (un seul
historique gardé). Écrire dans le journal ne doit jamais faire échouer une
réponse : une erreur d'écriture est tracée dans les logs applicatifs et ignorée.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

MAX_BYTES = 10 * 1024 * 1024
MAX_FIELD_CHARS = 2000  # un résultat d'outil est résumé, pas recopié en entier

_lock = threading.Lock()


def path() -> Path:
    return Path(settings.DATA_DIR) / "local_agent_audit.jsonl"


def _short(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
        return value[:MAX_FIELD_CHARS] + f"… [{len(value) - MAX_FIELD_CHARS} caractères de plus]"
    return value


def record(kind: str, conversation_id: str, **fields: Any) -> None:
    """Ajoute une ligne au journal."""
    entry = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "kind": kind,
        "conversation": conversation_id,
        **{key: _short(value) for key, value in fields.items()},
    }
    line = json.dumps(entry, ensure_ascii=False, default=str)
    target = path()
    try:
        with _lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.stat().st_size > MAX_BYTES:
                target.replace(target.with_suffix(".jsonl.1"))
            with target.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except OSError as exc:
        logger.warning("Agent local : journal d'audit non écrit (%s)", exc)


def tail(limit: int = 100) -> list[dict[str, Any]]:
    """Dernières lignes du journal, de la plus ancienne à la plus récente."""
    try:
        lines = path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries
