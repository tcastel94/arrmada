"""Épisodes manquants ou à venir (Sonarr) dans l'écran Série (watch_data.add_missing)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import watch_data as wd

PARIS = timezone(timedelta(hours=2))
NOW = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)


def _kodi(episodeid, season, number, playcount=0):
    return {
        "episodeid": episodeid,
        "season": season,
        "episode": number,
        "title": f"Kodi {season}x{number}",
        "playcount": playcount,
        "runtime": 3000,
    }


def _sonarr(season, number, air, has_file=False, monitored=True, title=""):
    return {
        "season": season,
        "episode": number,
        "title": title or f"Sonarr {season}x{number}",
        "air_date": air,
        "has_file": has_file,
        "monitored": monitored,
        "overview": "",
    }


SHOW = {"title": "Severance", "year": 2022}
KODI = [_kodi(1, 1, 1, playcount=1), _kodi(3, 1, 3), _kodi(4, 2, 1)]
SONARR = [
    _sonarr(1, 1, "2022-02-18T02:00:00Z", has_file=True),
    _sonarr(1, 2, "2022-02-18T02:00:00Z"),  # diffusé, pas de fichier → manquant
    _sonarr(1, 3, "2022-02-25T02:00:00Z", has_file=True),
    _sonarr(2, 1, "2025-01-17T02:00:00Z", has_file=True),
    _sonarr(2, 2, "2025-01-24T02:00:00Z", has_file=True),  # sur le NAS, pas dans Kodi
    _sonarr(2, 3, "2026-10-12T22:30:00Z"),  # à venir (13 octobre heure de Paris)
    _sonarr(3, 1, "", title="TBA"),  # saison 3 annoncée, date inconnue
    _sonarr(1, 4, "2022-03-04T02:00:00Z", monitored=False),  # non suivi : caché
    _sonarr(0, 1, "2022-01-01T00:00:00Z"),  # spéciaux : ignorés
]


def test_kinds():
    assert wd.missing_kind(SONARR[1], NOW) == "aired"
    assert wd.missing_kind(SONARR[4], NOW) == "nas"
    assert wd.missing_kind(SONARR[5], NOW) == "upcoming"
    assert wd.missing_kind(SONARR[6], NOW) == "tba"
    assert wd.missing_kind(SONARR[7], NOW) == ""


def test_missing_episodes_take_their_place():
    model = wd.build_show(SHOW, KODI)
    assert model["next_id"] == 3  # S01E03 : après le dernier vu
    full = wd.add_missing(model, SONARR, now=NOW, tz=PARIS)
    assert full["missing"] == 4
    season1 = full["episodes"][1]
    assert [(e["episode"], e.get("missing", "")) for e in season1] == [
        (1, ""),
        (2, "aired"),
        (3, ""),
    ]
    assert season1[1]["badge"] == "Manquant" and season1[1]["episodeid"] == 0
    assert season1[1]["status"] == "Manquant · OK pour le chercher"
    season2 = full["episodes"][2]
    assert [e.get("missing", "") for e in season2] == ["", "nas", "upcoming"]
    assert season2[2]["status"] == "Diffusion le 13 octobre 2026"  # heure de Paris
    # Saison 3 ajoutée, titre « TBA » remplacé
    assert [s["season"] for s in full["seasons"]] == [1, 2, 3]
    assert full["seasons"][2]["progress"] == "À venir"
    assert full["episodes"][3][0]["title"] == "Épisode 1"
    # L'épisode à suivre reste S01E03, désormais 3e de sa saison
    assert (full["start_season"], full["start_episode"]) == (0, 2)
    # Le modèle d'origine n'est pas modifié
    assert len(model["episodes"][1]) == 2


def test_nothing_missing_keeps_the_model():
    model = wd.build_show(SHOW, KODI)
    same = wd.add_missing(model, SONARR[:1] + SONARR[2:4], now=NOW)
    assert same == model
    assert wd.add_missing(model, [], now=NOW) == model


def test_missing_season_only():
    model = wd.build_show(SHOW, [_kodi(4, 2, 1, playcount=1)])  # tout vu
    full = wd.add_missing(model, [_sonarr(1, 1, "2022-02-18T02:00:00Z")], now=NOW)
    assert [s["season"] for s in full["seasons"]] == [1, 2]
    assert full["seasons"][0]["progress"] == "Manquante"
    # Rien à suivre : on reste sur la saison de départ d'origine (la 2)
    assert (full["start_season"], full["start_episode"]) == (1, 0)


def test_detail_line_without_repeats():
    full = wd.add_missing(wd.build_show(SHOW, KODI), SONARR, now=NOW, tz=PARIS)
    season1, season2 = full["episodes"][1], full["episodes"][2]
    assert wd.detail_line(season2[2]) == "Diffusion le 13 octobre 2026"  # date dite une fois
    assert wd.detail_line(season1[1]) == "Manquant · OK pour le chercher · 18 février 2022"
    # Épisode présent : état (s'il y en a un), diffusion, durée ; aucun « · » en trop
    assert wd.detail_line(season1[0]) == "Vu · 50 min"
    assert wd.detail_line({"status": "", "aired": "", "duration": ""}) == ""
