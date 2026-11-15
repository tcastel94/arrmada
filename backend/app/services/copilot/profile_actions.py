"""Outils qui changent les PROFILS QUALITÉ de Radarr / Sonarr (ADR-020).

L'agent savait dire « décoche Remux-2160p et mets le seuil sur Bluray-2160p » ;
il le fait maintenant lui-même, avec le même aperçu et la même validation que
les autres outils qui agissent (ADR-019) :

  - ``update_quality_profile`` : qualités autorisées, seuil (cutoff), mises à
    niveau ;
  - ``clone_quality_profile`` : copie d'un profil sous un autre nom (garder
    l'ancien réglage pour quelques titres, ou pouvoir revenir en arrière) ;
  - ``assign_quality_profile`` : passer des titres d'un profil à un autre ;
  - ``apply_trash_profile`` : créer ou mettre à jour un profil des TRaSH
    Guides (formats, scores, qualités), comme le bouton « Appliquer ».

Analogie exploitation : on modifie la définition d'un job, on ne relance ni ne
purge rien. Aucun de ces outils ne supprime un fichier, ne lance une recherche
ou ne re-télécharge quoi que ce soit ; ils changent seulement ce que le *arr
acceptera et cherchera ensuite. Le résultat rend l'état d'avant, pour que le
retour en arrière soit un simple appel inverse.

Le calcul (``_*_plan``) est fait deux fois, à l'aperçu puis à l'exécution : ce
qui est écrit part toujours de l'état lu à l'instant, jamais d'un aperçu vieux
de dix minutes.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from pydantic import Field

from app.services import trash_apply
from app.services.copilot import actions, tools
from app.services.copilot.actions import Preview
from app.services.copilot.tools import ManagerType, Tool, _Args

_KIND = {"radarr": "films", "sonarr": "séries"}
_LIBRARY = {"radarr": "/movie", "sonarr": "/series"}
_EDITOR = {"radarr": ("/movie/editor", "movieIds"), "sonarr": ("/series/editor", "seriesIds")}

_NOTHING_MOVES = (
    "Aucun fichier n'est supprimé ni re-téléchargé : seules les prochaines recherches changent"
)


class _Refused(Exception):
    """Demande impossible ou sans effet : le message est rendu au modèle, rien n'est demandé."""


# ══════════════════════════════════════════════════════════════
# Lecture d'un profil (pur)
# ══════════════════════════════════════════════════════════════


def _is_group(item: dict[str, Any]) -> bool:
    return not item.get("quality")


def _label(item: dict[str, Any]) -> str:
    return str(item.get("name") if _is_group(item) else item["quality"].get("name"))


def _item_id(item: dict[str, Any]) -> int:
    """Identifiant utilisable comme seuil : celui du groupe, ou de la qualité."""
    return int(item["id"] if _is_group(item) else item["quality"]["id"])


def _allowed_names(items: list[dict[str, Any]]) -> list[str]:
    """Qualités autorisées, à plat, de la meilleure à la moins bonne.

    Une qualité rangée dans un groupe suit le groupe : c'est lui qui est coché.
    """
    names: list[str] = []
    for item in reversed(items):
        if not item.get("allowed"):
            continue
        if _is_group(item):
            names.extend(_label(child) for child in reversed(item.get("items") or []))
        else:
            names.append(_label(item))
    return names


def _cutoff_choices(items: list[dict[str, Any]]) -> str:
    """Seuils possibles (lignes autorisées du profil), du meilleur au moins bon."""
    return ", ".join(_label(item) for item in reversed(items) if item.get("allowed"))


def _find_profile(profiles: list[dict[str, Any]], wanted: str) -> dict[str, Any]:
    """Profil par identifiant, par nom exact, sinon par morceau de nom s'il est unique."""
    text = wanted.strip()
    if text.isdigit():
        found = [p for p in profiles if p.get("id") == int(text)]
    else:
        folded = tools._fold(text)
        found = [p for p in profiles if tools._fold(p.get("name")) == folded]
        if not found:
            found = [p for p in profiles if folded in tools._fold(p.get("name"))]
    if len(found) == 1:
        return found[0]
    known = ", ".join(f"« {p.get('name')} » (id {p.get('id')})" for p in profiles)
    problem = "correspond à plusieurs profils" if found else "introuvable"
    raise _Refused(f"Profil « {wanted} » {problem}. Profils existants : {known}")


def _state(profile: dict[str, Any]) -> dict[str, Any]:
    """L'essentiel d'un profil, tel qu'on le redonnerait pour revenir en arrière."""
    return {
        "name": profile.get("name"),
        "cutoff": tools._cutoff_name(profile),
        "upgrade_allowed": profile.get("upgradeAllowed"),
        "allowed_qualities": _allowed_names(profile.get("items") or []),
    }


# ══════════════════════════════════════════════════════════════
# Modification des qualités (pur)
# ══════════════════════════════════════════════════════════════


def _set_allowed(
    items: list[dict[str, Any]], name: str, allowed: bool, dissolved: dict[int, int]
) -> bool:
    """Coche ou décoche une qualité (ou un groupe entier) ; False si elle est inconnue.

    Dans Radarr / Sonarr, un groupe se coche d'un bloc. Pour décocher une seule
    de ses qualités, on la sort du groupe, comme on le ferait à la souris. Un
    groupe réduit à une qualité redevient une qualité simple ; ``dissolved``
    retient alors {id du groupe: id de la qualité}, car le seuil peut le viser.
    """
    wanted = tools._fold(name)
    for index, item in enumerate(items):
        if tools._fold(_label(item)) == wanted:
            item["allowed"] = allowed
            for child in item.get("items") or []:
                child["allowed"] = allowed
            return True
        if not _is_group(item):
            continue
        children: list[dict[str, Any]] = item.get("items") or []
        for child in children:
            if tools._fold(_label(child)) != wanted:
                continue
            if bool(item.get("allowed")) == allowed:
                child["allowed"] = allowed
                return True
            children.remove(child)
            # Ordre de l'API : de la pire à la meilleure. La qualité sortie se
            # place juste au-dessus de son ancien groupe.
            items.insert(index + 1, {"quality": child["quality"], "items": [], "allowed": allowed})
            if len(children) == 1:
                last = children[0]
                dissolved[int(item["id"])] = int(last["quality"]["id"])
                items[index] = {
                    "quality": last["quality"],
                    "items": [],
                    "allowed": bool(item.get("allowed")),
                }
            return True
    return False


def _cutoff_target(items: list[dict[str, Any]], name: str) -> int | None:
    """Identifiant du seuil demandé : une ligne autorisée, ou le groupe qui contient la qualité."""
    wanted = tools._fold(name)
    for item in items:
        if not item.get("allowed"):
            continue
        if tools._fold(_label(item)) == wanted:
            return _item_id(item)
        if any(tools._fold(_label(child)) == wanted for child in item.get("items") or []):
            return _item_id(item)
    return None


def _rank(items: list[dict[str, Any]], cutoff: Any) -> int:
    """Position du seuil dans le profil (plus grand = meilleure qualité)."""
    return next((i for i, item in enumerate(items) if _item_id(item) == cutoff), -1)


@dataclass
class _Change:
    before: dict[str, Any]
    after: dict[str, Any]
    lines: list[str] = field(default_factory=list)
    #: le changement peut faire chercher de meilleures versions de fichiers déjà là
    may_upgrade: bool = False


def _switch(value: Any) -> str:
    return "activées" if value else "désactivées"


def change_profile(
    profile: dict[str, Any],
    *,
    allow: list[str],
    disallow: list[str],
    cutoff: str,
    upgrade_allowed: bool | None,
) -> _Change:
    """Profil modifié + description du changement ; ``_Refused`` s'il est impossible ou nul."""
    if not (allow or disallow or cutoff or upgrade_allowed is not None):
        raise _Refused("Aucun changement demandé pour ce profil")
    after = copy.deepcopy(profile)
    items: list[dict[str, Any]] = after.get("items") or []
    dissolved: dict[int, int] = {}
    unknown = [n for n in allow if not _set_allowed(items, n, True, dissolved)]
    unknown += [n for n in disallow if not _set_allowed(items, n, False, dissolved)]
    if unknown:
        every = ", ".join(
            _label(q) for q in reversed(trash_apply._flatten(profile.get("items") or []))
        )
        raise _Refused(f"Qualité inconnue : {', '.join(unknown)}. Qualités de ce service : {every}")
    if not any(item.get("allowed") for item in items):
        raise _Refused("Un profil doit garder au moins une qualité autorisée")

    current = dissolved.get(after.get("cutoff"), after.get("cutoff"))
    if cutoff:
        target = _cutoff_target(items, cutoff)
        if target is None:
            raise _Refused(
                f"« {cutoff} » ne peut pas servir de seuil : ce n'est pas une qualité autorisée "
                f"du profil. Choix possibles : {_cutoff_choices(items)}"
            )
        current = target
    elif current not in {_item_id(item) for item in items if item.get("allowed")}:
        raise _Refused(
            f"Le seuil actuel « {tools._cutoff_name(profile)} » ne serait plus autorisé : "
            f"précise le nouveau seuil (cutoff) parmi : {_cutoff_choices(items)}"
        )
    after["cutoff"] = current
    if upgrade_allowed is not None:
        after["upgradeAllowed"] = upgrade_allowed

    was, now = _allowed_names(profile.get("items") or []), _allowed_names(items)
    removed = [n for n in was if n not in now]
    added = [n for n in now if n not in was]
    change = _Change(before=profile, after=after)
    if removed:
        change.lines.append(f"Qualités retirées : {', '.join(removed)}")
    if added:
        change.lines.append(f"Qualités ajoutées : {', '.join(added)}")
    old_cutoff, new_cutoff = tools._cutoff_name(profile), tools._cutoff_name(after)
    if old_cutoff != new_cutoff:
        change.lines.append(f"Seuil : {old_cutoff} → {new_cutoff}")
    if bool(profile.get("upgradeAllowed")) != bool(after.get("upgradeAllowed")):
        change.lines.append(
            f"Mises à niveau : {_switch(profile.get('upgradeAllowed'))} → "
            f"{_switch(after.get('upgradeAllowed'))}"
        )
    if not change.lines:
        raise _Refused(f"Le profil « {profile.get('name')} » est déjà dans cet état")

    raised = _rank(items, current) > _rank(profile.get("items") or [], profile.get("cutoff"))
    turned_on = bool(after.get("upgradeAllowed")) and not profile.get("upgradeAllowed")
    change.may_upgrade = bool(after.get("upgradeAllowed")) and (bool(added) or raised or turned_on)
    return change


# ══════════════════════════════════════════════════════════════
# Arguments
# ══════════════════════════════════════════════════════════════

_SERVICE = "radarr (films) ou sonarr (séries)."
_PROFILE = "Nom du profil qualité, ou son id (tous deux renvoyés par get_quality_profiles)."


class UpdateProfileArgs(_Args):
    service: ManagerType = Field(description=_SERVICE)
    profile: str = Field(min_length=1, description=_PROFILE)
    disallow: list[str] = Field(
        default_factory=list,
        max_length=40,
        description="Qualités à décocher (ex. « Remux-2160p »), ou nom d'un groupe entier "
        "(ex. « WEB 2160p »). Noms tels que renvoyés par get_quality_profiles.",
    )
    allow: list[str] = Field(
        default_factory=list, max_length=40, description="Qualités ou groupes à cocher."
    )
    cutoff: str = Field(
        default="",
        description="Nouveau seuil (cutoff) : la qualité à partir de laquelle le *arr arrête "
        "de chercher mieux. Doit rester autorisée. Vide : seuil inchangé. Obligatoire si le "
        "seuil actuel fait partie des qualités décochées.",
    )
    upgrade_allowed: bool | None = Field(
        default=None,
        description="true / false : autoriser les mises à niveau jusqu'au seuil. Absent : inchangé.",
    )


class CloneProfileArgs(_Args):
    service: ManagerType = Field(description=_SERVICE)
    profile: str = Field(min_length=1, description="Profil à copier. " + _PROFILE)
    new_name: str = Field(min_length=1, max_length=100, description="Nom de la copie.")


class AssignProfileArgs(_Args):
    service: ManagerType = Field(description=_SERVICE)
    profile: str = Field(min_length=1, description="Profil à attribuer. " + _PROFILE)
    titles: list[str] = Field(
        default_factory=list,
        max_length=200,
        description="Titres visés, tels que dans la médiathèque (search_library) ; ajoute "
        "l'année entre parenthèses s'il y a des homonymes : « Dune (2021) ».",
    )
    from_profile: str = Field(
        default="",
        description="À la place de `titles` : tous les titres qui utilisent ce profil (nom ou id).",
    )


class TrashProfileArgs(_Args):
    service: ManagerType = Field(description=_SERVICE)
    profile: str = Field(
        min_length=1,
        description="Profil des TRaSH Guides : son nom ou son `id`, renvoyés par "
        "search_trash_guides (kind=quality_profiles).",
    )
    apply_sizes: bool = Field(
        default=False,
        description="true : applique aussi les tailles de qualité recommandées par TRaSH "
        "(réglage global du service, commun à tous les profils).",
    )


# ══════════════════════════════════════════════════════════════
# Modifier un profil
# ══════════════════════════════════════════════════════════════


async def _read(service: str, *, library: bool) -> tuple[list[dict[str, Any]], list[Any]]:
    """(profils, médiathèque) du service ; la médiathèque seulement si demandée."""
    client = await actions._arr(service)
    try:
        profiles = await client.get("/qualityprofile")
        titles = await client.get(_LIBRARY[service]) if library else []
    finally:
        await client.close()
    return list(profiles or []), list(titles or [])


def _used_by(titles: list[Any], profile: dict[str, Any]) -> int:
    return sum(1 for t in titles if t.get("qualityProfileId") == profile.get("id"))


async def _update_plan(args: UpdateProfileArgs) -> tuple[_Change, int]:
    profiles, titles = await _read(args.service, library=True)
    profile = _find_profile(profiles, args.profile)
    change = change_profile(
        profile,
        allow=args.allow,
        disallow=args.disallow,
        cutoff=args.cutoff,
        upgrade_allowed=args.upgrade_allowed,
    )
    return change, _used_by(titles, profile)


async def preview_update(args: UpdateProfileArgs) -> Preview:
    try:
        change, used_by = await _update_plan(args)
    except _Refused as exc:
        return Preview(str(exc), actionable=False)
    kind = _KIND[args.service]
    app = actions._APP[args.service]
    return Preview(
        f"Modifier le profil « {change.before.get('name')} » de {app}",
        details=[*change.lines, f"Utilisé par {used_by} {kind}", _NOTHING_MOVES],
        warning=(
            f"{app} pourra chercher une meilleure version des {kind} de ce profil "
            "(re-téléchargements)"
            if change.may_upgrade and used_by
            else ""
        ),
    )


async def update_quality_profile(args: UpdateProfileArgs) -> dict[str, Any]:
    try:
        change, used_by = await _update_plan(args)
    except _Refused as exc:
        return {"status": "nothing", "message": str(exc)}
    client = await actions._arr(args.service)
    try:
        await client.put(f"/qualityprofile/{change.before['id']}", data=change.after)
    finally:
        await client.close()
    return {
        "status": "ok",
        "message": f"Profil « {change.before.get('name')} » modifié : " + " ; ".join(change.lines),
        "used_by_titles": used_by,
        "before": _state(change.before),
        "after": _state(change.after),
    }


# ══════════════════════════════════════════════════════════════
# Copier un profil
# ══════════════════════════════════════════════════════════════


async def _clone_plan(args: CloneProfileArgs) -> dict[str, Any]:
    profiles, _titles = await _read(args.service, library=False)
    source = _find_profile(profiles, args.profile)
    name = args.new_name.strip()
    if any(tools._fold(p.get("name")) == tools._fold(name) for p in profiles):
        raise _Refused(f"Un profil « {name} » existe déjà : choisis un autre nom")
    payload = copy.deepcopy(source)
    payload.pop("id", None)
    payload["name"] = name
    return payload | {"_source": source.get("name")}


async def preview_clone(args: CloneProfileArgs) -> Preview:
    try:
        payload = await _clone_plan(args)
    except _Refused as exc:
        return Preview(str(exc), actionable=False)
    state = _state(payload)
    return Preview(
        f"Créer le profil « {payload['name']} » dans {actions._APP[args.service]}, "
        f"copie de « {payload['_source']} »",
        details=[
            f"Seuil : {state['cutoff']}",
            f"Qualités autorisées : {', '.join(state['allowed_qualities'])}",
            "Le nouveau profil n'est attribué à aucun titre",
        ],
    )


async def clone_quality_profile(args: CloneProfileArgs) -> dict[str, Any]:
    try:
        payload = await _clone_plan(args)
    except _Refused as exc:
        return {"status": "nothing", "message": str(exc)}
    source = payload.pop("_source")
    client = await actions._arr(args.service)
    try:
        created = await client.post("/qualityprofile", data=payload)
    finally:
        await client.close()
    return {
        "status": "ok",
        "message": f"Profil « {payload['name']} » créé, copie de « {source} »",
        "id": (created or {}).get("id"),
    }


# ══════════════════════════════════════════════════════════════
# Attribuer un profil à des titres
# ══════════════════════════════════════════════════════════════


def _title(item: dict[str, Any]) -> str:
    return f"{item.get('title')} ({item.get('year')})" if item.get("year") else str(item["title"])


def _match_titles(library: list[Any], wanted: list[str]) -> list[dict[str, Any]]:
    """Un titre de la médiathèque par demande ; refuse dès qu'un nom est inconnu ou ambigu."""
    found: dict[int, dict[str, Any]] = {}
    problems: list[str] = []
    for name in wanted:
        folded = tools._fold(name).strip()
        matches = [
            item
            for item in library
            if folded in (tools._fold(item.get("title")), tools._fold(_title(item)))
        ]
        if not matches:
            matches = [item for item in library if folded in tools._fold(_title(item))]
        if len(matches) == 1:
            found[matches[0]["id"]] = matches[0]
        elif matches:
            choices = ", ".join(_title(item) for item in matches[:6])
            problems.append(f"« {name} » correspond à plusieurs titres ({choices})")
        else:
            problems.append(f"« {name} » introuvable")
    if problems:
        raise _Refused(
            "Titres à préciser (nom exact, avec l'année entre parenthèses) : "
            + " ; ".join(problems)
        )
    return list(found.values())


async def _assign_plan(args: AssignProfileArgs) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(profil cible, titres qui changent de profil)."""
    if bool(args.titles) == bool(args.from_profile):
        raise _Refused("Indique soit `titles`, soit `from_profile` (l'un des deux)")
    profiles, library = await _read(args.service, library=True)
    target = _find_profile(profiles, args.profile)
    if args.from_profile:
        source = _find_profile(profiles, args.from_profile)
        chosen = [t for t in library if t.get("qualityProfileId") == source.get("id")]
    else:
        chosen = _match_titles(library, args.titles)
    moving = [t for t in chosen if t.get("qualityProfileId") != target.get("id")]
    if not moving:
        raise _Refused(
            f"Rien à changer : aucun titre visé, ou ils utilisent déjà « {target.get('name')} »"
        )
    return target, moving


async def preview_assign(args: AssignProfileArgs) -> Preview:
    try:
        target, moving = await _assign_plan(args)
    except _Refused as exc:
        return Preview(str(exc), actionable=False)
    kind = _KIND[args.service]
    names = sorted(_title(t) for t in moving)
    details = names[:20]
    if len(names) > 20:
        details.append(f"… et {len(names) - 20} autres")
    details.append(_NOTHING_MOVES)
    return Preview(
        f"Passer {len(moving)} {kind} au profil « {target.get('name')} » "
        f"dans {actions._APP[args.service]}",
        details=details,
    )


async def assign_quality_profile(args: AssignProfileArgs) -> dict[str, Any]:
    try:
        target, moving = await _assign_plan(args)
    except _Refused as exc:
        return {"status": "nothing", "message": str(exc)}
    path, ids_key = _EDITOR[args.service]
    previous: dict[Any, int] = {}
    for item in moving:
        previous[item.get("qualityProfileId")] = previous.get(item.get("qualityProfileId"), 0) + 1
    client = await actions._arr(args.service)
    try:
        await client.put(
            path, data={ids_key: [t["id"] for t in moving], "qualityProfileId": target["id"]}
        )
    finally:
        await client.close()
    return {
        "status": "ok",
        "message": f"{len(moving)} {_KIND[args.service]} passés au profil « {target.get('name')} »",
        "changed": len(moving),
        "previous_profile_ids": previous,
    }


# ══════════════════════════════════════════════════════════════
# Appliquer un profil des TRaSH Guides
# ══════════════════════════════════════════════════════════════


def _compact(text: Any) -> str:
    """Lettres et chiffres seuls : « [French MULTi.VF] UHD » se retrouve sans ses crochets."""
    return "".join(ch for ch in tools._fold(text) if ch.isalnum())


async def _trash_plan(args: TrashProfileArgs) -> tuple[trash_apply.ProfilePlan, list[Any]]:
    from app.services import trash_guides

    cache = trash_guides.get_trash_cache()
    if cache.is_stale or not cache.get_quality_profiles(args.service):
        await cache.sync()  # données de plus de 24 h : on repart des guides du jour
    profiles = cache.get_quality_profiles(args.service)
    wanted = _compact(args.profile)
    found = [
        p for p in profiles if wanted in (_compact(trash_apply._stem(p)), _compact(p.get("name")))
    ]
    if not found:
        found = [p for p in profiles if wanted in _compact(p.get("name"))]
    if len(found) != 1:
        problem = "correspond à plusieurs profils TRaSH" if found else "introuvable dans TRaSH"
        near = ", ".join(f"« {p.get('name')} »" for p in (found or profiles)[:12])
        raise _Refused(f"« {args.profile} » {problem}. Profils proches : {near}")
    plan = trash_apply.build_profile_plan(cache, args.service, trash_apply._stem(found[0]))
    if plan is None:
        raise _Refused(f"Profil TRaSH « {args.profile} » illisible")
    sizes = trash_apply.build_size_plan(cache, args.service) if args.apply_sizes else []
    return plan, sizes


async def _trash_report(args: TrashProfileArgs, *, dry_run: bool) -> trash_apply.ApplyReport:
    plan, sizes = await _trash_plan(args)
    client = await actions._arr(args.service)
    try:
        return await trash_apply.apply_plans(client, args.service, [plan], sizes, dry_run=dry_run)
    finally:
        await client.close()


def _trash_counts(report: trash_apply.ApplyReport) -> list[str]:
    lines = []
    if report.cfs_created:
        lines.append(f"{len(report.cfs_created)} formats personnalisés créés")
    if report.cfs_updated:
        lines.append(f"{len(report.cfs_updated)} formats personnalisés mis à jour")
    if report.sizes:
        lines.append(f"{len(report.sizes)} tailles de qualité ajustées")
    return lines


async def preview_trash(args: TrashProfileArgs) -> Preview:
    try:
        report = await _trash_report(args, dry_run=True)
    except _Refused as exc:
        return Preview(str(exc), actionable=False)
    if report.errors or not report.profiles:
        reason = " ; ".join(report.errors) or "profil non calculable"
        return Preview(f"Profil TRaSH inapplicable : {reason}", actionable=False)
    profile = report.profiles[0]
    counts = _trash_counts(report)
    if profile["action"] == "unchanged" and not counts:
        return Preview(
            f"Le profil « {profile['name']} » est déjà conforme aux TRaSH Guides", actionable=False
        )
    app = actions._APP[args.service]
    verb = {"created": "Créer", "updated": "Mettre à jour", "unchanged": "Compléter"}
    return Preview(
        f"{verb[profile['action']]} le profil TRaSH « {profile['name']} » dans {app}",
        details=[
            *counts,
            f"Seuil : {profile['cutoff']}",
            f"Qualités autorisées : {', '.join(profile['qualities'])}",
            f"Score minimum {profile['min_format_score']}, "
            f"score d'arrêt {profile['cutoff_format_score']}",
            *report.warnings[:5],
            _NOTHING_MOVES,
        ],
        warning=(
            "Le profil du même nom existe déjà : ses qualités et ses scores sont remplacés "
            "par ceux de TRaSH"
            if profile["action"] == "updated"
            else ""
        ),
    )


async def apply_trash_profile(args: TrashProfileArgs) -> dict[str, Any]:
    try:
        report = await _trash_report(args, dry_run=False)
    except _Refused as exc:
        return {"status": "nothing", "message": str(exc)}
    if not report.profiles:
        return {"status": "error", "message": " ; ".join(report.errors) or "profil non appliqué"}
    profile = report.profiles[0]
    done = {"created": "créé", "updated": "mis à jour", "unchanged": "déjà conforme"}
    return {
        "status": "error" if report.errors else "ok",
        "message": f"Profil TRaSH « {profile['name']} » {done[profile['action']]}"
        + (f" ({', '.join(_trash_counts(report))})" if _trash_counts(report) else ""),
        "profile_id": profile.get("id"),
        "cutoff": profile["cutoff"],
        "qualities": profile["qualities"],
        "warnings": report.warnings,
        "errors": report.errors,
    }


# ══════════════════════════════════════════════════════════════
# Registre
# ══════════════════════════════════════════════════════════════

TOOLS: tuple[Tool, ...] = (
    Tool(
        "update_quality_profile",
        "Modifier un profil qualité",
        "AGIT. Modifie un profil qualité de Radarr ou Sonarr : décocher ou cocher des qualités "
        "(disallow / allow), changer le seuil (cutoff), autoriser ou non les mises à niveau. "
        "Ne touche ni aux scores des formats ni aux fichiers : rien n'est supprimé ni "
        "re-téléchargé, seules les prochaines recherches changent. Le résultat rend l'état "
        "d'avant, pour pouvoir revenir en arrière. Lis d'abord get_quality_profiles.",
        UpdateProfileArgs,
        update_quality_profile,
        preview_update,
    ),
    Tool(
        "clone_quality_profile",
        "Copier un profil qualité",
        "AGIT. Crée un profil qualité identique à un profil existant, sous un autre nom. Sert "
        "à garder l'ancien réglage (ex. un profil « Remux » pour quelques films de référence) "
        "avant de modifier l'original. La copie n'est attribuée à aucun titre.",
        CloneProfileArgs,
        clone_quality_profile,
        preview_clone,
    ),
    Tool(
        "assign_quality_profile",
        "Attribuer un profil qualité",
        "AGIT. Change le profil qualité de films (radarr) ou de séries (sonarr) : soit une "
        "liste de titres (titles), soit tous les titres d'un autre profil (from_profile). "
        "Rien n'est re-téléchargé sur le moment ; le nouveau profil joue sur les prochaines "
        "recherches et mises à niveau.",
        AssignProfileArgs,
        assign_quality_profile,
        preview_assign,
    ),
    Tool(
        "apply_trash_profile",
        "Appliquer un profil TRaSH",
        "AGIT. Crée ou met à jour dans Radarr ou Sonarr un profil qualité des TRaSH Guides, "
        "sous son nom TRaSH : ses formats personnalisés, leurs scores, ses qualités et son "
        "seuil (même calcul que le bouton « Appliquer » d'ArrMada). Resynchronise d'abord les "
        "guides s'ils datent de plus de 24 h. Le profil créé n'est attribué à aucun titre : "
        "enchaîne avec assign_quality_profile si la personne le veut.",
        TrashProfileArgs,
        apply_trash_profile,
        preview_trash,
    ),
)
