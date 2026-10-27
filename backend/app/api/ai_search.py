"""AI-powered search — natural language media queries.

The LLM (local Ollama first, OpenRouter as fallback) turns the query into
structured filters, which are then applied to the cached media library.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.services import media_aggregator
from app.services.llm import LLMUnavailableError, ai_configured, chat_json, parse_json_object
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/search/ai",
    tags=["ai-search"],
    dependencies=[Depends(get_current_user)],
)

SYSTEM_PROMPT = """Tu es un assistant de recherche pour une médiathèque de films et séries.
L'utilisateur décrit ce qu'il cherche en langage naturel.
Tu dois extraire des filtres structurés depuis sa requête.

Réponds UNIQUEMENT avec un objet JSON valide (pas de markdown, pas de texte autour) :
{
  "type": "movie" | "series" | null,
  "genres": ["action", "horreur", ...] ou [],
  "year_min": 1990 ou null,
  "year_max": 2025 ou null,
  "quality_keywords": ["4K", "2160p", "Remux", "1080p", ...] ou [],
  "title_keywords": ["batman", "marvel", ...] ou [],
  "size_filter": "large" | "small" | null,
  "has_file": true | false | null,
  "sort_by": "year" | "size" | "title" | "quality" | null,
  "sort_order": "asc" | "desc" | null,
  "description": "courte description de ce que l'utilisateur cherche, en français"
}

Exemples :
- "films d'action des années 90" → {"type":"movie","genres":["action"],"year_min":1990,"year_max":1999,...}
- "séries que j'ai pas encore" → {"type":"series","has_file":false,...}
- "gros fichiers remux" → {"quality_keywords":["Remux"],"size_filter":"large",...}
- "les batman" → {"title_keywords":["batman"],...}
"""


async def _call_llm(user_query: str) -> tuple[dict[str, Any], str]:
    """Extract structured filters from natural language.

    Returns ``(filters, engine_name)``; raises :class:`LLMUnavailableError`
    when no engine answered.
    """
    content, engine = await chat_json(
        SYSTEM_PROMPT,
        user_query,
        temperature=0.1,
        ollama_max_tokens=300,
        # First query after a while also loads the model into memory.
        ollama_timeout=60,
        openrouter_max_tokens=300,
        openrouter_timeout=15,
        purpose="Recherche IA",
    )
    return parse_json_object(content), engine


def _apply_filters(media: list[dict], filters: dict[str, Any]) -> list[dict]:
    """Apply extracted AI filters to the media list."""
    results = list(media)

    # Type filter
    if filters.get("type"):
        results = [m for m in results if m.get("type") == filters["type"]]

    # Year range
    year_min = filters.get("year_min")
    year_max = filters.get("year_max")
    if year_min:
        results = [m for m in results if (m.get("year") or 0) >= year_min]
    if year_max:
        results = [m for m in results if (m.get("year") or 9999) <= year_max]

    # Genre filter (case-insensitive partial match)
    genres = filters.get("genres", [])
    if genres:
        genre_lower = [g.lower() for g in genres]
        results = [
            m
            for m in results
            if any(gl in g.lower() for g in (m.get("genres") or []) for gl in genre_lower)
        ]

    # Title keywords
    title_kw = filters.get("title_keywords", [])
    if title_kw:
        kw_lower = [k.lower() for k in title_kw]
        results = [
            m for m in results if any(kw in (m.get("title") or "").lower() for kw in kw_lower)
        ]

    # Quality keywords
    quality_kw = filters.get("quality_keywords", [])
    if quality_kw:
        kw_lower = [k.lower() for k in quality_kw]
        results = [
            m for m in results if any(kw in (m.get("quality") or "").lower() for kw in kw_lower)
        ]

    # Has file filter
    has_file = filters.get("has_file")
    if has_file is not None:
        results = [m for m in results if m.get("has_file") == has_file]

    # Size filter
    size_filter = filters.get("size_filter")
    if size_filter == "large":
        results.sort(key=lambda m: m.get("size_bytes", 0), reverse=True)
    elif size_filter == "small":
        results.sort(key=lambda m: m.get("size_bytes", 0))

    # Sorting
    sort_by = filters.get("sort_by")
    sort_order = filters.get("sort_order", "desc")
    if sort_by:
        reverse = sort_order == "desc"
        if sort_by == "year":
            results.sort(key=lambda m: m.get("year") or 0, reverse=reverse)
        elif sort_by == "size":
            results.sort(key=lambda m: m.get("size_bytes", 0), reverse=reverse)
        elif sort_by == "title":
            results.sort(key=lambda m: (m.get("title") or "").lower(), reverse=reverse)

    return results


@router.get("")
async def ai_search(
    q: str = Query(..., min_length=3, description="Natural language search query"),
    db: AsyncSession = Depends(get_db),
):
    """AI-powered natural language search across the media library."""
    if not ai_configured():
        return {
            "error": "Recherche IA non configurée (ni OLLAMA_URL ni OPENROUTER_API_KEY)",
            "items": [],
            "filters": {},
            "ai_available": False,
        }

    # 1. Extract filters from natural language
    try:
        filters, engine = await _call_llm(q)
    except LLMUnavailableError as exc:
        return {"error": str(exc), "items": [], "filters": {}, "ai_available": True}
    except Exception as exc:  # noqa: BLE001 — unreadable LLM reply
        logger.error("AI filter extraction failed: %s", exc)
        return {
            "error": f"Réponse IA illisible : {exc}",
            "items": [],
            "filters": {},
            "ai_available": True,
        }

    # 2. Fetch full media library (cached)
    media = await media_aggregator.cached_library(db)

    # 3. Apply filters
    results = _apply_filters(media, filters)

    return {
        "query": q,
        "description": filters.get("description", ""),
        "filters": filters,
        "items": results[:50],
        "total": len(results),
        "ai_available": True,
        "engine": engine,
    }
