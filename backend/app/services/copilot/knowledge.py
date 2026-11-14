"""Documents ArrMada consultables par le copilote : ADR, CHANGELOG, README, guides.

Pas d'index vectoriel : une quinzaine de fichiers Markdown, découpés par
titre et cherchés par mots-clés, comme un ``grep`` qui renverrait la section
entière plutôt que la ligne. Le modèle lit ensuite le document (ou une de
ses sections) avec ``read``.

Où sont les fichiers :
- dans l'image Docker : ``/app/knowledge`` (copiés par le Dockerfile) ;
- depuis un clone Git (développement, tests) : la racine du dépôt ;
- ailleurs : ``COPILOT_KNOWLEDGE_DIR``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Au-delà, un document n'est pas renvoyé d'un bloc : sommaire + début, et le
# modèle demande la section voulue (le CHANGELOG pèse plus de 200 Ko).
MAX_READ_CHARS = 20_000
MAX_EXCERPT_CHARS = 700
MAX_RESULTS = 8

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
_WORD_RE = re.compile(r"[a-z0-9]{2,}")


@dataclass(frozen=True)
class Section:
    """Une section d'un document : son fil de titres et son texte."""

    heading: str  # « Décision › Lecture directe »
    text: str


@dataclass(frozen=True)
class Document:
    doc_id: str  # « adr-012 », « changelog », « readme »…
    title: str
    kind: str  # adr | changelog | guide
    text: str
    sections: list[Section] = field(default_factory=list)


def fold(text: str) -> str:
    """Minuscules sans accents : « Qualité » et « qualite » se trouvent l'un l'autre."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(fold(text))


def _split_sections(text: str) -> list[Section]:
    """Découpe un Markdown par titres (jusqu'au niveau 4), en gardant le fil des titres."""
    sections: list[Section] = []
    trail: list[tuple[int, str]] = []
    buffer: list[str] = []
    in_code = False

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if body:
            heading = " › ".join(title for _, title in trail) or "(introduction)"
            sections.append(Section(heading=heading, text=body))
        buffer.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        match = None if in_code else _HEADING_RE.match(line)
        if match:
            flush()
            level = len(match.group(1))
            while trail and trail[-1][0] >= level:
                trail.pop()
            trail.append((level, match.group(2)))
            continue
        buffer.append(line)
    flush()
    return sections


def _title_of(text: str, fallback: str) -> str:
    """Premier titre de niveau 1, hors blocs de code (« # commentaire » d'un script)."""
    in_code = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        match = None if in_code else _HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            return match.group(2)
    return fallback


def _candidate_roots() -> list[Path]:
    here = Path(__file__).resolve()
    roots = []
    if settings.COPILOT_KNOWLEDGE_DIR:
        roots.append(Path(settings.COPILOT_KNOWLEDGE_DIR))
    roots.append(here.parents[3] / "knowledge")  # image Docker : /app/knowledge
    roots.append(here.parents[4])  # clone Git : racine du dépôt
    return roots


def _files_of(root: Path) -> list[tuple[str, str, Path]]:
    """(identifiant, type, fichier) des documents trouvés sous une racine."""
    found: list[tuple[str, str, Path]] = []
    for adr_dir in (root / "adr", root / "docs" / "adr"):
        for path in sorted(adr_dir.glob("*.md")):
            number = path.stem.split("-", 1)[0]
            found.append((f"adr-{number}", "adr", path))
    changelog = root / "CHANGELOG.md"
    if changelog.is_file():
        found.append(("changelog", "changelog", changelog))
    readme = root / "README.md"
    if readme.is_file():
        found.append(("readme", "guide", readme))
    for guide_dir in (root / "guides", root / "docs"):
        for path in sorted(guide_dir.glob("*.md")):
            found.append((path.stem.lower(), "guide", path))
    return found


_documents: dict[str, Document] | None = None


def load(*, force: bool = False) -> dict[str, Document]:
    """Documents disponibles, par identifiant (lus une fois par processus)."""
    global _documents
    if _documents is not None and not force:
        return _documents

    documents: dict[str, Document] = {}
    for root in _candidate_roots():
        try:
            files = _files_of(root) if root.is_dir() else []
        except OSError as exc:
            logger.warning("Copilote : dossier de documents illisible (%s) : %s", root, exc)
            files = []
        # Une racine ne compte que si elle contient des décisions d'architecture :
        # sinon le /app de l'image (sans docs) masquerait /app/knowledge.
        if not any(kind == "adr" for _, kind, _ in files):
            continue
        for doc_id, kind, path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Copilote : %s illisible : %s", path, exc)
                continue
            documents[doc_id] = Document(
                doc_id=doc_id,
                title=_title_of(text, path.stem),
                kind=kind,
                text=text,
                sections=_split_sections(text),
            )
        break
    if not documents:
        logger.info("Copilote : aucun document ArrMada trouvé (ADR, CHANGELOG)")
    _documents = documents
    return documents


def catalog() -> list[dict[str, str]]:
    """Liste courte des documents (identifiant, titre, type), pour la consigne système."""
    return [
        {"id": doc.doc_id, "title": doc.title, "kind": doc.kind}
        for doc in sorted(load().values(), key=lambda d: d.doc_id)
    ]


def _excerpt(text: str, words: list[str]) -> str:
    folded = fold(text)
    positions = [pos for word in words if (pos := folded.find(word)) >= 0]
    start = max(0, min(positions, default=0) - 120)
    excerpt = text[start : start + MAX_EXCERPT_CHARS].strip()
    prefix = "… " if start > 0 else ""
    suffix = " …" if start + MAX_EXCERPT_CHARS < len(text) else ""
    return f"{prefix}{excerpt}{suffix}"


def search(query: str, *, limit: int = MAX_RESULTS) -> list[dict[str, str | int]]:
    """Sections les plus pertinentes pour une question, tous documents confondus."""
    words = list(dict.fromkeys(_tokens(query)))
    if not words:
        return []
    scored: list[tuple[int, Document, Section]] = []
    for doc in load().values():
        for section in doc.sections:
            heading = fold(section.heading)
            body = fold(section.text)
            matched = [w for w in words if w in heading or w in body]
            if not matched:
                continue
            # Un mot trouvé dans le titre pèse plus ; tous les mots trouvés, davantage encore.
            score = sum(min(body.count(w), 5) + 6 * (w in heading) for w in matched)
            score += 10 * len(matched)
            if len(matched) == len(words):
                score += 15
            scored.append((score, doc, section))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "doc": doc.doc_id,
            "title": doc.title,
            "section": section.heading,
            "score": score,
            "excerpt": _excerpt(section.text, words),
        }
        for score, doc, section in scored[:limit]
    ]


def read(doc_id: str, section: str = "") -> dict[str, object]:
    """Un document entier, ou les sections dont le titre contient ``section``."""
    documents = load()
    doc = documents.get(doc_id.strip().lower())
    if doc is None:
        return {
            "error": f"Document inconnu : {doc_id!r}",
            "available": [d["id"] for d in catalog()],
        }

    if section.strip():
        wanted = fold(section)
        matches = [s for s in doc.sections if wanted in fold(s.heading)]
        if not matches:
            return {
                "error": f"Aucune section « {section} » dans {doc.doc_id}",
                "sections": [s.heading for s in doc.sections][:200],
            }
        body = "\n\n".join(f"## {s.heading}\n{s.text}" for s in matches)
        truncated = len(body) > MAX_READ_CHARS
        return {
            "doc": doc.doc_id,
            "title": doc.title,
            "sections": [s.heading for s in matches][:60],
            "text": body[:MAX_READ_CHARS],
            "truncated": truncated,
            **(
                {
                    "note": f"{len(matches)} sections correspondent et le tout est trop long : "
                    "précise `section` avec un titre plus distinctif."
                }
                if truncated
                else {}
            ),
        }

    if len(doc.text) <= MAX_READ_CHARS:
        return {"doc": doc.doc_id, "title": doc.title, "text": doc.text, "truncated": False}
    return {
        "doc": doc.doc_id,
        "title": doc.title,
        "text": doc.text[:MAX_READ_CHARS],
        "truncated": True,
        "note": "Document long : seul le début est renvoyé. Redemande avec `section` "
        "(un extrait d'un des titres ci-dessous) pour lire la suite.",
        "sections": [s.heading for s in doc.sections][:200],
    }
