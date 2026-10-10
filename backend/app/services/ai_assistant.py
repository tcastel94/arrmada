"""AI Assistant service for natural language discovery using local Ollama (Gemma)."""

from __future__ import annotations

import os

import httpx

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Config Ollama
OLLAMA_URL = os.environ.get("OLLAMA_URL") or "http://192.168.2.3:11434"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL") or "gemma4:e4b"


async def _call_ollama(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    """Helper function to call Ollama Chat API."""
    if not OLLAMA_URL:
        logger.warning("OLLAMA_URL not set. AI discovery disabled.")
        return "⚠️ L'assistant IA n'est pas configuré (Ollama introuvable)."

    url = f"{OLLAMA_URL.rstrip('/')}/api/generate"

    prompt = f"{system_prompt}\n\n{user_prompt}"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }

    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
    except Exception as e:
        logger.error(f"Error calling Ollama API ({OLLAMA_MODEL}): {e}")
        return "❌ Désolé, je n'ai pas pu contacter l'IA locale (Ollama) pour le moment. Vérifiez qu'elle est bien lancée."


async def suggest_media(prompt: str) -> str:
    """Uses Ollama (Gemma) to suggest movies/shows based on a natural language prompt."""
    system_prompt = (
        "Tu es un expert en cinéma et séries. Le client va te demander des recommandations "
        "en langage naturel (ex: 'Un bon thriller des années 2010'). "
        "Tu dois répondre avec une liste de 3 à 5 recommandations très pertinentes. "
        "Pour chaque recommandation, inclus le titre, l'année, et un très court résumé sans spoiler. "
        "Formate ta réponse de manière agréable pour Telegram (HTML)."
    )
    return await _call_ollama(system_prompt, prompt, temperature=0.7)


async def generate_weekly_summary(added_movies: list[str], added_shows: list[str]) -> str:
    """Generates a weekly summary of added media using Ollama to make it fun."""

    if not added_movies and not added_shows:
        return "ℹ️ Bilan Hebdo : Aucun nouveau contenu ajouté cette semaine."

    movies_str = ", ".join(added_movies) if added_movies else "Aucun film"
    shows_str = ", ".join(added_shows) if added_shows else "Aucune série"

    system_prompt = (
        "Tu es le majordome virtuel d'un cinéma privé haut de gamme. "
        "Rédige un bilan hebdomadaire fun et accrocheur des films et séries ajoutés cette semaine. "
        "Mets en valeur les ajouts importants de façon synthétique et élégante. Formate pour Telegram (HTML). "
        "N'invente pas de films, utilise uniquement la liste fournie."
    )

    user_prompt = (
        f"Films ajoutés cette semaine : {movies_str}\nSéries ajoutées cette semaine : {shows_str}"
    )

    return await _call_ollama(system_prompt, user_prompt, temperature=0.8)
