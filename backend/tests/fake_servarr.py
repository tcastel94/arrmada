"""Faux Radarr / Sonarr AVEC ÉTAT, pour tester l'application TRaSH.

Contrairement à fake_arr.py (réponses figées), celui-ci garde en mémoire ce
qu'on lui écrit (formats, profils, tailles, bascules) et applique les mêmes
contrôles qu'un vrai service, relevés sur Radarr 6.4 et Sonarr 4.0.20 :

  - un profil doit lister CHAQUE qualité du service une seule fois ;
  - le palier d'arrêt (cutoff) doit être une qualité ou un groupe autorisé ;
  - les scores doivent viser des formats existants ;
  - une condition de langue reçoit un champ ``exceptLanguage: false`` qu'on
    ne lui a pas envoyé (comportement réel, qui piégeait la comparaison).

Les réponses de départ (schéma de profil, définitions de qualité, langues,
profils par défaut) sont de vraies réponses capturées : tests/fixtures/arr/.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).parent / "fixtures" / "arr"
VERSIONS = {"radarr": "6.4.4.10685", "sonarr": "4.0.20.3014"}


def _load(service: str, name: str) -> Any:
    return json.loads((FIXTURES / f"{service}_{name}.json").read_text(encoding="utf-8"))


def _flatten(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        out.append(item)
        out.extend(_flatten(item.get("items") or []))
    return out


class FakeServarr:
    def __init__(self, service: str, *, version: str | None = None) -> None:
        self.service = service
        self.version = version or VERSIONS[service]
        self.schema = _load(service, "qualityprofile_schema")
        self.profiles: list[dict[str, Any]] = _load(service, "qualityprofile")
        self.definitions: list[dict[str, Any]] = _load(service, "qualitydefinition")
        self.languages = _load(service, "language")
        self.custom_formats: list[dict[str, Any]] = []
        self.library: list[dict[str, Any]] = []
        #: (méthode, chemin) de chaque écriture reçue
        self.writes: list[tuple[str, str]] = []
        self._next_id = 100

    # ── Helpers ───────────────────────────────────────────
    def _id(self) -> int:
        self._next_id += 1
        return self._next_id

    def _quality_ids(self) -> list[int]:
        return sorted(
            i["quality"]["id"] for i in _flatten(self.schema["items"]) if i.get("quality")
        )

    def _validate_profile(self, profile: dict[str, Any]) -> str | None:
        ids = sorted(i["quality"]["id"] for i in _flatten(profile["items"]) if i.get("quality"))
        if ids != self._quality_ids():
            return "Must contain all qualities"
        allowed = {
            (i["quality"]["id"] if i.get("quality") else i.get("id"))
            for i in profile["items"]
            if i.get("allowed")
        }
        if profile.get("cutoff") not in allowed:
            return "Cutoff must be an allowed quality or group"
        known = {cf["id"] for cf in self.custom_formats}
        if any(f["format"] not in known for f in profile.get("formatItems", [])):
            return "Unknown custom format"
        return None

    @staticmethod
    def _normalize_cf(cf: dict[str, Any]) -> dict[str, Any]:
        cf = copy.deepcopy(cf)
        for spec in cf.get("specifications", []):
            names = {f["name"] for f in spec.get("fields", [])}
            if (
                spec.get("implementation") == "LanguageSpecification"
                and "exceptLanguage" not in names
            ):
                spec["fields"].append({"name": "exceptLanguage", "value": False})
        return cf

    # ── Transport httpx ───────────────────────────────────
    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v3")
        method = request.method
        body = json.loads(request.content) if request.content else None
        if method != "GET":
            self.writes.append((method, path))

        if method == "GET" and path == "/system/status":
            return httpx.Response(200, json={"version": self.version})
        if method == "GET" and path == "/qualityprofile/schema":
            return httpx.Response(200, json=copy.deepcopy(self.schema))
        if method == "GET" and path == "/qualityprofile":
            return httpx.Response(200, json=copy.deepcopy(self.profiles))
        if method == "GET" and path == "/qualitydefinition":
            return httpx.Response(200, json=copy.deepcopy(self.definitions))
        if method == "GET" and path == "/language":
            return httpx.Response(200, json=self.languages)
        if method == "GET" and path == "/customformat":
            return httpx.Response(200, json=copy.deepcopy(self.custom_formats))
        if method == "GET" and path in ("/movie", "/series"):
            return httpx.Response(200, json=copy.deepcopy(self.library))

        if method == "POST" and path == "/customformat":
            if any(cf["name"].lower() == body["name"].lower() for cf in self.custom_formats):
                return httpx.Response(400, json=[{"errorMessage": "Must be unique"}])
            cf = self._normalize_cf({**body, "id": self._id()})
            self.custom_formats.append(cf)
            return httpx.Response(201, json=cf)
        m = re.fullmatch(r"/customformat/(\d+)", path)
        if method == "PUT" and m:
            cf = self._normalize_cf({**body, "id": int(m.group(1))})
            self.custom_formats = [cf if c["id"] == cf["id"] else c for c in self.custom_formats]
            return httpx.Response(202, json=cf)

        if method == "POST" and path == "/qualityprofile":
            if error := self._validate_profile(body):
                return httpx.Response(400, json=[{"errorMessage": error}])
            profile = {**body, "id": self._id()}
            self.profiles.append(profile)
            return httpx.Response(201, json=profile)
        m = re.fullmatch(r"/qualityprofile/(\d+)", path)
        if method == "PUT" and m:
            if error := self._validate_profile(body):
                return httpx.Response(400, json=[{"errorMessage": error}])
            profile = {**body, "id": int(m.group(1))}
            self.profiles = [profile if p["id"] == profile["id"] else p for p in self.profiles]
            return httpx.Response(202, json=profile)

        if method == "PUT" and path == "/qualitydefinition/update":
            by_id = {d["id"]: d for d in body}
            self.definitions = [by_id.get(d["id"], d) for d in self.definitions]
            return httpx.Response(202, json=body)

        if method == "PUT" and path in ("/movie/editor", "/series/editor"):
            ids = set(body.get("movieIds") or body.get("seriesIds") or [])
            for item in self.library:
                if item["id"] in ids:
                    item["qualityProfileId"] = body["qualityProfileId"]
            return httpx.Response(202, json=[])

        return httpx.Response(404, json={"message": f"route inconnue {method} {path}"})

    def client(self) -> Any:
        """ArrBaseClient branché sur ce faux service (aucun réseau)."""
        from app.services.arr_client import ArrBaseClient

        client = ArrBaseClient(url=f"http://{self.service}.test", api_key="k")
        client.API_PREFIX = "/api/v3"
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(self.handle)
        )
        return client


def load_trash_cache(tmp_path: Path) -> Any:
    """Cache TRaSH rempli avec l'extrait figé de tests/fixtures/trash/."""
    import time

    from app.services.trash_guides import TrashGuidesCache

    cache = TrashGuidesCache(cache_dir=tmp_path)
    base = Path(__file__).parent / "fixtures" / "trash"
    for service in ("radarr", "sonarr"):
        data = json.loads((base / f"{service}.json").read_text(encoding="utf-8"))
        cache._data[f"{service}_cf"] = data["cf"]
        cache._data[f"{service}_cfg"] = data["cfg"]
        cache._data[f"{service}_qp"] = data["qp"]
        cache._data[f"{service}_qs"] = data["qs"]
    cache._data["sonarr_naming"] = []
    cache._last_sync = time.time()
    return cache
