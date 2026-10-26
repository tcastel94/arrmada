"""Tests de la sonde de détection (stack/probe.py) et du diagnostic de « Tester ».

Faux réseau : chaque hôte a un comportement, reproduit d'après de vrais
Radarr 6.4 / Sonarr 4.0 / Prowlarr 2.0 et les vraies exceptions de httpx :

  - ``ok``       : /ping → 200 {"status": "OK"}, system/status → 200 ;
  - ``auth``     : /ping → 200, system/status → 401 (clé refusée ou absente) ;
  - ``starting`` : 503 (proxy devant une appli qui démarre) ;
  - ``refused``  : httpx.ConnectError « All connection attempts failed »,
                   causé par ConnectionRefusedError (errno 111) ;
  - ``dns``      : httpx.ConnectError causé par socket.gaierror (errno -2) ;
  - ``timeout``  : httpx.ConnectTimeout au texte vide (hairpin Synology) ;
  - ``sonarr``   : un Sonarr répond sur le port demandé (mauvaise appli).

Un hôte absent de la table se comporte comme ``dns`` (nom inconnu).
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from app.services.stack import probe
from app.services.stack.configs import FoundConfig

KEY = "64efe45ba1eb4c2a9acb8740345f5f4d"


def _radarr(**kw: Any) -> FoundConfig:
    return FoundConfig(
        type="radarr", name="Radarr", port=7878, source="radarr/config.xml", api_key=KEY, **kw
    )


def refused() -> httpx.ConnectError:
    """Port fermé, tel que httpx 0.28 + anyio 4 le lève (relevé en vrai) :
    ConnectError « All connection attempts failed », causé par un OSError
    du même texte, lui-même causé par ConnectionRefusedError (errno 111)."""
    try:
        try:
            raise ConnectionRefusedError(111, "Connect call failed ('192.168.1.49', 7878)")
        except ConnectionRefusedError as root:
            raise OSError("All connection attempts failed") from root
    except OSError as os_err:
        exc = httpx.ConnectError("All connection attempts failed")
        exc.__cause__ = os_err
        return exc


def unknown_name() -> httpx.ConnectError:
    """Nom inconnu : ConnectError causé par socket.gaierror (errno -2)."""
    exc = httpx.ConnectError("[Errno -2] Name or service not known")
    exc.__cause__ = socket.gaierror(-2, "Name or service not known")
    return exc


def timed_out() -> httpx.ConnectTimeout:
    """Hôte muet (hairpin) : ConnectTimeout au texte vide, causé par TimeoutError."""
    exc = httpx.ConnectTimeout("")
    exc.__cause__ = TimeoutError()
    return exc


class FakeNet:
    """Hôte → comportement, avec le décompte des requêtes reçues."""

    def __init__(self, hosts: dict[str, str | list[str]]) -> None:
        # Une liste = comportements successifs, un par essai (le dernier reste)
        self.hosts = {h: b if isinstance(b, list) else [b] for h, b in hosts.items()}
        self.current: dict[str, str] = {}
        #: hôte → nombre d'essais (un essai commence par /ping)
        self.calls: dict[str, int] = {}

    def handle(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        path = request.url.path
        seq = self.hosts.get(host, ["dns"])
        if path.endswith("/ping"):
            self.calls[host] = self.calls.get(host, 0) + 1
            self.current[host] = seq.pop(0) if len(seq) > 1 else seq[0]
        kind = self.current.get(host, seq[0])
        if kind == "timeout":
            raise timed_out()
        if kind == "refused":
            raise refused()
        if kind == "dns":
            raise unknown_name()
        if kind == "starting":
            return httpx.Response(503, text="Service Unavailable")
        if path.endswith("/ping"):
            return httpx.Response(200, json={"status": "OK"})
        if kind == "auth" or request.headers.get("X-Api-Key") != KEY:
            return httpx.Response(401)
        app = "Sonarr" if kind == "sonarr" else "Radarr"
        return httpx.Response(200, json={"appName": app, "version": "6.4.4.10685"})


@pytest.fixture
def net(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, Any]], FakeNet]:
    """Installe un faux réseau sur les httpx.AsyncClient créés ensuite."""
    monkeypatch.setattr(probe, "default_gateway", lambda: None)

    def install(hosts: dict[str, Any]) -> FakeNet:
        fake = FakeNet(hosts)
        original_init = httpx.AsyncClient.__init__

        def patched_init(self: httpx.AsyncClient, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("transport", httpx.MockTransport(fake.handle))
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
        return fake

    return install


# ── Ordre des adresses ────────────────────────────────────────
async def test_docker_name_first_when_it_answers(net: Callable) -> None:
    """Synology : l'IP du NAS répond aussi (port publié), mais le nom Docker
    passe devant, car c'est lui que les autres conteneurs sauront joindre."""
    net({"192.168.1.49": "ok", "radarr": "ok"})
    endpoint = await probe.locate(_radarr(), user_hosts=["192.168.1.49"], retry_delays=())
    assert endpoint.urls[0] == "http://radarr:7878"
    assert "http://192.168.1.49:7878" in endpoint.urls
    assert endpoint.version == "6.4.4.10685"
    assert endpoint.error is None


async def test_lan_kept_when_no_docker_name(net: Callable) -> None:
    """Appli hors Docker (ou ArrMada sur un autre réseau) : LAN d'abord, comme avant."""
    net({"192.168.1.49": "ok"})
    endpoint = await probe.locate(_radarr(), user_hosts=["192.168.1.49"], retry_delays=())
    assert endpoint.urls == ["http://192.168.1.49:7878"]
    assert endpoint.failures == {"radarr": "dns", "host.docker.internal": "dns"}


async def test_url_base_kept(net: Callable) -> None:
    net({"radarr": "ok"})
    endpoint = await probe.locate(_radarr(url_base="/radarr"), retry_delays=())
    assert endpoint.urls == ["http://radarr:7878/radarr"]


# ── Erreurs distinctes ────────────────────────────────────────
@pytest.mark.parametrize(
    ("behaviour", "expected"),
    [
        ("auth", "refuse la clé API"),
        ("starting", "en cours de démarrage"),
        ("sonarr", "Une autre application que Radarr répond sur le port 7878"),
        ("refused", "Connexion refusée sur le port 7878"),
        ("timeout", "même réseau Docker"),
    ],
)
async def test_failure_messages(net: Callable, behaviour: str, expected: str) -> None:
    net({"192.168.1.49": behaviour})
    endpoint = await probe.locate(_radarr(), user_hosts=["192.168.1.49"], retry_delays=())
    assert endpoint.urls == []
    assert expected in (endpoint.error or "")
    assert "Injoignable" not in (endpoint.error or "")
    # Le détail par hôte suit : on sait ce qui a été essayé
    assert "192.168.1.49 (" in (endpoint.error or "")
    assert "radarr (nom inconnu)" in (endpoint.error or "")


async def test_most_useful_failure_wins(net: Callable) -> None:
    """Clé refusée sur un hôte, délai dépassé sur l'autre : on parle de la clé."""
    net({"192.168.1.49": "timeout", "radarr": "auth"})
    endpoint = await probe.locate(_radarr(), user_hosts=["192.168.1.49"], retry_delays=())
    assert "refuse la clé API" in (endpoint.error or "")
    assert endpoint.failures["192.168.1.49"] == "timeout"
    assert endpoint.failures["radarr"] == "auth"


async def test_ping_without_key_then_authenticated_call(net: Callable) -> None:
    """Le /ping part SANS clé, l'appel authentifié AVEC."""
    seen: list[tuple[str, str | None]] = []
    fake = net({"radarr": "ok"})
    original = fake.handle

    def spy(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("X-Api-Key")))
        return original(request)

    fake.handle = spy  # type: ignore[method-assign]
    await probe.locate(_radarr(), retry_delays=())
    radarr = [s for s in seen if s[0].startswith(("/ping", "/api"))]
    assert ("/ping", None) in radarr
    assert ("/api/v3/system/status", KEY) in radarr


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        # Chaînes de causes réelles (httpx 0.28 + anyio 4)
        (refused(), "refused"),
        (unknown_name(), "dns"),
        (timed_out(), "timeout"),
        (httpx.ReadTimeout(""), "timeout"),
        # Repli sur le texte quand la cause manque
        (httpx.ConnectError("[Errno 111] Connection refused"), "refused"),
        (httpx.ConnectError("[Errno -3] Temporary failure in name resolution"), "dns"),
        (httpx.ConnectError("[SSL: WRONG_VERSION_NUMBER] wrong version number"), "tls"),
        (httpx.RemoteProtocolError("Server disconnected"), "network"),
    ],
)
def test_classify_error(exc: Exception, kind: str) -> None:
    assert probe.classify_error(exc) == kind


async def test_classify_real_closed_port() -> None:
    """Vrai port fermé sur 127.0.0.1 : protège contre un changement de httpx
    ou d'anyio dans la forme de l'exception."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
        with pytest.raises(httpx.HTTPError) as info:
            await client.get(f"http://127.0.0.1:{port}/ping")
    assert probe.classify_error(info.value) == "refused"


# ── Nouvel essai au démarrage ─────────────────────────────────
async def test_retry_while_container_starts(net: Callable) -> None:
    """Conteneur tout juste lancé : le nom se résout mais rien n'écoute encore
    (refus), puis l'appli répond. Seul l'hôte concerné est réessayé."""
    fake = net({"radarr": ["refused", "starting", "ok"], "192.168.1.49": "timeout"})
    endpoint = await probe.locate(_radarr(), user_hosts=["192.168.1.49"], retry_delays=(0, 0))
    assert endpoint.urls == ["http://radarr:7878"]
    assert fake.calls["radarr"] == 3
    assert fake.calls["192.168.1.49"] == 1  # un délai dépassé n'est pas réessayé


async def test_retry_gives_up_after_the_last_delay(net: Callable) -> None:
    fake = net({"radarr": "starting"})
    endpoint = await probe.locate(_radarr(), retry_delays=(0, 0))
    assert endpoint.urls == []
    assert fake.calls["radarr"] == 3
    assert "en cours de démarrage" in (endpoint.error or "")


async def test_no_retry_when_something_answers(net: Callable) -> None:
    fake = net({"radarr": "ok", "192.168.1.49": "starting"})
    await probe.locate(_radarr(), user_hosts=["192.168.1.49"], retry_delays=(0, 0))
    assert fake.calls["192.168.1.49"] == 1


# ── Diagnostic de « Tester » ──────────────────────────────────
async def test_diagnose_suggests_docker_name(net: Callable) -> None:
    net({"192.168.1.49": "timeout", "radarr": "ok"})
    diag = await probe.diagnose_url("radarr", "http://192.168.1.49:7878", KEY, "Radarr")
    assert not diag.ok
    assert diag.kind == "timeout"
    assert diag.suggested_url == "http://radarr:7878"
    assert diag.message == (
        "Délai dépassé sur 192.168.1.49:7878 : depuis le conteneur ArrMada, cette adresse ne "
        "répond pas (fréquent avec l'IP du NAS sur Synology)."
    )


async def test_diagnose_timeout_without_docker_name(net: Callable) -> None:
    """Aucun nom ne répond : là, le conseil du réseau Docker partagé est le bon."""
    net({"192.168.1.49": "timeout"})
    diag = await probe.diagnose_url("radarr", "http://192.168.1.49:7878", KEY, "Radarr")
    assert diag.suggested_url is None
    assert "même réseau Docker que Radarr" in (diag.message or "")
    assert "essayé" not in (diag.message or "")


async def test_diagnose_uses_service_name_slug(net: Callable) -> None:
    """Deuxième instance : le conteneur s'appelle comme le service (« Radarr 4K »)."""
    net({"192.168.1.49": "refused", "radarr-4k": "ok"})
    diag = await probe.diagnose_url("radarr", "http://192.168.1.49:7878/4k", KEY, "Radarr 4K")
    assert diag.suggested_url == "http://radarr-4k:7878/4k"


async def test_diagnose_ok_and_no_suggestion(net: Callable) -> None:
    net({"192.168.1.49": "ok", "radarr": "ok"})
    diag = await probe.diagnose_url("radarr", "http://192.168.1.49:7878", KEY, "Radarr")
    assert diag.ok and diag.suggested_url is None and diag.message is None


async def test_diagnose_wrong_key_everywhere(net: Callable) -> None:
    """Clé refusée : changer d'adresse ne servirait à rien, on ne propose rien."""
    net({"192.168.1.49": "auth", "radarr": "auth"})
    diag = await probe.diagnose_url("radarr", "http://192.168.1.49:7878", KEY, "Radarr")
    assert diag.kind == "auth"
    assert diag.suggested_url is None
    assert "refuse la clé API" in (diag.message or "")


async def test_test_endpoint_returns_diagnosis(
    client: AsyncClient, auth_headers: dict[str, str], net: Callable
) -> None:
    """POST /api/services/{id}/test : hors ligne + cause + URL proposée."""
    resp = await client.post(
        "/api/services",
        json={
            "name": "Radarr",
            "type": "radarr",
            "url": "http://192.168.1.49:7878",
            "api_key": KEY,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    service_id = resp.json()["id"]

    net({"192.168.1.49": "timeout", "radarr": "ok"})
    body = (await client.post(f"/api/services/{service_id}/test", headers=auth_headers)).json()
    assert body["success"] is False
    assert body["status"] == "offline"
    assert body["suggested_url"] == "http://radarr:7878"
    assert "Délai dépassé" in body["diagnosis"]

    # L'utilisateur accepte la proposition : l'URL est mise à jour, le test passe
    resp = await client.put(
        f"/api/services/{service_id}", json={"url": body["suggested_url"]}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = (await client.post(f"/api/services/{service_id}/test", headers=auth_headers)).json()
    assert body["success"] is True
    assert body["diagnosis"] is None and body["suggested_url"] is None


async def test_draft_test_returns_diagnosis(
    client: AsyncClient, auth_headers: dict[str, str], net: Callable
) -> None:
    """« Tester » dans le formulaire, avant d'enregistrer."""
    net({"192.168.1.49": "timeout", "radarr": "ok"})
    body = (
        await client.post(
            "/api/services/test",
            json={"type": "radarr", "url": "http://192.168.1.49:7878", "api_key": KEY},
            headers=auth_headers,
        )
    ).json()
    assert body["success"] is False
    assert body["suggested_url"] == "http://radarr:7878"
