"""ArrMada admin CLI — run inside the container.

    docker exec -it arrmada arrmada-cli set-password     # prompt for a new one
    docker exec -it arrmada arrmada-cli reset-password   # back to "unclaimed"
    docker exec -it arrmada arrmada-cli status

``reset-password`` deletes the hash: the next visitor of the web UI is asked
to create a new password, so only use it on a trusted network.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.services import auth_store


def _set_password() -> int:
    first = getpass.getpass("Nouveau mot de passe : ")
    if len(first) < auth_store.MIN_PASSWORD_LENGTH:
        print(f"Trop court (minimum {auth_store.MIN_PASSWORD_LENGTH} caractères).", file=sys.stderr)
        return 1
    if getpass.getpass("Confirmation : ") != first:
        print("Les deux saisies diffèrent.", file=sys.stderr)
        return 1
    auth_store.set_password(first)
    print("Mot de passe enregistré.")
    return 0


def _reset_password() -> int:
    auth_store.clear_password()
    if auth_store.password_source() == "env":
        print("Hash supprimé, mais ARRMADA_AUTH_SECRET est défini : il redevient le mot de passe.")
    else:
        print("Mot de passe supprimé : l'interface web demandera d'en créer un nouveau.")
    return 0


def _status() -> int:
    labels = {
        "file": "défini (haché dans le dossier data)",
        "env": "hérité de ARRMADA_AUTH_SECRET (.env)",
        "none": "aucun — l'instance attend sa configuration",
    }
    print(f"Mot de passe admin : {labels[auth_store.password_source()]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arrmada-cli", description="Administration ArrMada")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("set-password", help="définir un nouveau mot de passe admin")
    sub.add_parser("reset-password", help="supprimer le mot de passe (re-création via l'UI)")
    sub.add_parser("status", help="afficher l'état du mot de passe")
    args = parser.parse_args(argv)

    handlers = {
        "set-password": _set_password,
        "reset-password": _reset_password,
        "status": _status,
    }
    return handlers[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
