"""Essai de l'agent local en ligne de commande, sans passer par l'interface.

@author : Jeff Pomponne <jpomponne@gmail.com>

Depuis l'hôte (le conteneur a déjà la base, le .env et l'accès aux *arr) ::

    docker exec -it arrmada python -m app.services.local_agent "Qu'est-ce qui sort cette semaine ?"

Sans argument : mode conversation (une question par ligne, Ctrl-D pour sortir).
Chaque appel d'outil est affiché avec ses paramètres et sa durée : on voit ce
que le modèle a décidé avant de lire sa réponse.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from app.config import settings
from app.services.local_agent import agent, conversations, ollama


async def _ask(conversation: conversations.Conversation, question: str) -> None:
    started = time.monotonic()
    async for event, data in agent.run_turn(conversation, question):
        if event == "text":
            print(data["delta"], end="", flush=True)
        elif event == "tool_start":
            arguments = json.dumps(data["input"], ensure_ascii=False)
            print(f"\n  → {data['name']} {arguments}", end="", flush=True)
        elif event == "tool_end":
            print(f"  [{'ok' if data['ok'] else 'ÉCHEC'}, {data['duration_ms']} ms]", flush=True)
        elif event in ("notice", "error"):
            print(f"\n[{event}] {data['message']}", flush=True)
        elif event == "usage":
            turn = data["turn"]
            print(
                f"\n  ({data['model']} · {data['model_calls']} appel(s) au modèle · "
                f"{turn['input_tokens']} jetons lus · {turn['output_tokens']} écrits · "
                f"{time.monotonic() - started:.1f} s)"
            )


async def main() -> int:
    if not ollama.is_configured():
        print("OLLAMA_URL n'est pas renseigné dans le .env.", file=sys.stderr)
        return 1
    print(
        f"Agent local · {settings.LOCAL_AGENT_MODEL} · num_ctx={settings.LOCAL_AGENT_NUM_CTX} · "
        f"keep_alive={settings.LOCAL_AGENT_KEEP_ALIVE}",
        file=sys.stderr,
    )
    conversation = conversations.create()
    if len(sys.argv) > 1:
        await _ask(conversation, " ".join(sys.argv[1:]))
        return 0
    while True:
        try:
            question = input("\n> ").strip()
        except EOFError:
            print()
            return 0
        if question:
            await _ask(conversation, question)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
