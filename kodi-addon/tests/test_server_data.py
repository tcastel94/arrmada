"""Adresse du serveur ArrMada (1.25.2) : plus jamais d'IP inventée."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import server_data as sd

ADDON = Path(__file__).resolve().parent.parent / "script.arrmada"


class TestNormalizeUrl:
    @pytest.mark.parametrize("raw", ["", "   ", None, "/"])
    def test_empty_stays_empty(self, raw) -> None:
        """Rien de réglé : « non configuré », surtout pas l'IP d'un autre réseau."""
        assert sd.normalize_url(raw) == ""

    @pytest.mark.parametrize(
        "raw",
        ["http://127.0.0.1:8420", "localhost:8420", "http://LOCALHOST", "http://[::1]:8420"],
    )
    def test_the_tv_itself_is_not_a_server(self, raw: str) -> None:
        assert sd.normalize_url(raw) == ""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # TV déjà configurée : son adresse reste utilisée telle quelle
            ("http://192.168.1.49:8420", "http://192.168.1.49:8420"),
            ("https://arrmada.example.org", "https://arrmada.example.org"),
            ("http://nas:8420/arrmada", "http://nas:8420/arrmada"),
            # Schéma ajouté, « / » final et espaces retirés
            ("  nas:8420/ ", "http://nas:8420"),
            # Port de la web app (3420) → port de l'API (8420), comme avant
            ("http://192.168.1.49:3420", "http://192.168.1.49:8420"),
            ("nas:3420/", "http://nas:8420"),
            ("http://[fd00::5]:3420", "http://[fd00::5]:8420"),
            # Seul le PORT 3420 change, pas un autre nombre qui le contient
            ("http://nas:34200", "http://nas:34200"),
            ("http://nas-3420.lan:8420", "http://nas-3420.lan:8420"),
        ],
    )
    def test_configured_address(self, raw: str, expected: str) -> None:
        assert sd.normalize_url(raw) == expected

    def test_odd_port_is_kept_as_typed(self) -> None:
        """Port illisible : on ne devine rien, l'erreur de connexion le dira."""
        assert sd.normalize_url("nas:abc") == "http://nas:abc"


class TestResolveServerUrl:
    def test_setting_wins(self) -> None:
        assert sd.resolve_server_url("http://nas:8420", "http://autre:8420") == "http://nas:8420"

    def test_paired_server_when_setting_is_empty(self) -> None:
        """TV appairée qui se fiait à l'ancienne valeur par défaut : elle la retrouve."""
        assert sd.resolve_server_url("", "http://192.168.1.49:8420") == "http://192.168.1.49:8420"
        assert sd.resolve_server_url("localhost", "http://nas:8420") == "http://nas:8420"

    def test_nothing_known(self) -> None:
        assert sd.resolve_server_url("", "") == ""
        assert sd.resolve_server_url("", "http://127.0.0.1:8420") == ""


class TestNotConfiguredError:
    def test_same_shape_as_the_other_api_errors(self) -> None:
        error = sd.not_configured_error()
        assert error["status"] == "error"
        assert error["message"].startswith("Serveur ArrMada non configuré")
        assert "code" not in error  # pas un code HTTP : le serveur n'a pas été appelé
        assert sd.is_not_configured(error)

    def test_other_errors(self) -> None:
        for response in (
            {"status": "error", "message": "Connexion impossible", "code": 500},
            {"status": "error", "code": 401},
            {},
            None,
            [],
        ):
            assert not sd.is_not_configured(response)

    def test_fresh_dict_each_time(self) -> None:
        """Les écrans copient la réponse (listing.LAST_ERROR) : jamais d'objet partagé."""
        first = sd.not_configured_error()
        first["message"] = "modifié"
        assert sd.not_configured_error()["message"] == sd.NOT_CONFIGURED_MESSAGE


class TestNetworkScan:
    def test_scan_the_tv_subnet_without_the_tv(self) -> None:
        hosts = sd.scan_hosts("192.168.1.37")
        assert len(hosts) == 253
        assert hosts[0] == "192.168.1.1"
        assert hosts[-1] == "192.168.1.254"
        assert "192.168.1.37" not in hosts
        assert "192.168.1.0" not in hosts and "192.168.1.255" not in hosts

    @pytest.mark.parametrize(
        "ip", ["", "  ", "pas une ip", "127.0.0.1", "169.254.3.4", "8.8.8.8", "fe80::1"]
    )
    def test_nothing_to_scan(self, ip: str) -> None:
        """IP inconnue, boucle locale, sans DHCP ou publique : saisie à la main."""
        assert sd.scan_hosts(ip) == []

    def test_candidate_url(self) -> None:
        assert sd.candidate_url("192.168.1.49") == "http://192.168.1.49:8420"

    def test_only_an_arrmada_health_answer_counts(self) -> None:
        assert sd.is_arrmada_health({"status": "ok", "service": "arrmada", "version": "1.40.0"})
        assert sd.is_arrmada_health({"service": "ArrMada"})
        # Autre service qui répond sur le port 8420, réponse inattendue
        assert not sd.is_arrmada_health({"status": "ok", "service": "sabnzbd"})
        assert not sd.is_arrmada_health({"status": "ok"})
        assert not sd.is_arrmada_health(["arrmada"])
        assert not sd.is_arrmada_health(None)

    def test_found_label(self) -> None:
        url = "http://192.168.1.49:8420"
        assert sd.found_label(url, {"version": "1.40.2"}) == f"{url} · ArrMada 1.40.2"
        assert sd.found_label(url, {}) == f"{url} · ArrMada"

    def test_sort_hosts_numerically(self) -> None:
        urls = ["http://192.168.1.10:8420", "http://192.168.1.9:8420", "http://nas:8420"]
        assert sd.sort_hosts(urls) == [
            "http://192.168.1.9:8420",
            "http://192.168.1.10:8420",
            "http://nas:8420",
        ]


class TestNoHardCodedAddress:
    """Le dépôt est public : aucune IP du réseau du mainteneur dans l'add-on."""

    def test_server_url_has_no_default(self) -> None:
        root = ET.parse(ADDON / "resources" / "settings.xml").getroot()
        setting = root.find(".//setting[@id='server_url']")
        assert setting is not None
        assert setting.get("default") == ""

    def test_no_private_ip_in_the_api_client(self) -> None:
        source = (ADDON / "lib" / "api.py").read_text(encoding="utf-8")
        assert not re.search(r"192\.168\.\d+\.\d+", source)
        assert 'setSetting("server_url", "http' not in source
