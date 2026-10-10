"""Appairage de la TV (ADR-003 § 4) : logique pure de l'écran d'appairage."""

from __future__ import annotations

import pytest

import pairing_data as pd


def test_format_code() -> None:
    assert pd.format_code("k7p4qx") == "K7P 4QX"
    assert pd.format_code("ABC") == "ABC"  # format inattendu : affiché tel quel


def test_code_tiles_always_six() -> None:
    assert pd.code_tiles("K7P4QX") == ["K", "7", "P", "4", "Q", "X"]
    assert pd.code_tiles("AB") == ["A", "B", " ", " ", " ", " "]
    assert pd.code_tiles("") == [" "] * 6


@pytest.mark.parametrize(
    ("build", "platform", "expected"),
    [
        ("21.1 (21.1.0) Git:20240818-dac7b8c8d1", "Android", "Kodi 21.1 · Android"),
        ("20.5", "", "Kodi 20.5"),
        ("", "Linux", "Kodi · Linux"),
    ],
)
def test_platform_label(build: str, platform: str, expected: str) -> None:
    assert pd.platform_label(build, platform) == expected


@pytest.mark.parametrize(
    ("seconds", "expected"), [(582, "9:42"), (60, "1:00"), (5.9, "0:05"), (-3, "0:00")]
)
def test_countdown(seconds: float, expected: str) -> None:
    assert pd.fmt_countdown(seconds) == expected


def test_web_hint_drops_the_code() -> None:
    url = "http://192.168.2.3:3420/settings/kodi?pair=K7P4QX"
    assert pd.web_hint(url) == "http://192.168.2.3:3420/settings/kodi"


@pytest.mark.parametrize(
    ("response", "state"),
    [
        ({"status": "pending", "interval": 3}, "pending"),
        ({"status": "ok", "token": "abc", "device": {}}, "ok"),
        ({"status": "ok"}, "error"),  # « ok » sans jeton : on ne l'accepte pas
        ({"status": "error", "code": 410, "message": "Code expiré"}, "expired"),
        ({"status": "error", "message": "Connexion impossible"}, "error"),
        (None, "error"),
    ],
)
def test_poll_outcome(response, state: str) -> None:
    assert pd.poll_outcome(response)[0] == state


def test_device_summary() -> None:
    device = {"name": "Shield Cinéma", "room": "cinema", "avr_name": "Yamaha RX-A2080"}
    assert pd.device_summary(device) == "Shield Cinéma · Salle de cinéma · Yamaha RX-A2080"
    assert (
        pd.device_summary({"name": "Shield", "room": "salon", "avr_name": None}) == "Shield · Salon"
    )


class TestMigration:
    """Ancien mot de passe → appairage automatique (phase 3)."""

    def test_room_from_the_old_setting(self) -> None:
        assert pd.migration_room("cinema") == "cinema"
        assert pd.migration_room(" Salon ") == "salon"
        assert pd.migration_room("") == "salon"
        assert pd.migration_room("garage") == "salon"

    def test_confirm_outcome(self) -> None:
        assert pd.migration_confirm_outcome({"status": "ok"}) == "ok"
        # Mot de passe refusé ou demande invalide : inutile de réessayer
        for code in (401, 403, 422):
            refused = {"status": "error", "message": "Not authenticated", "code": code}
            assert pd.migration_confirm_outcome(refused) == "refused"
        # Serveur injoignable ou erreur passagère : on réessaiera
        assert pd.migration_confirm_outcome({"status": "error", "message": "x"}) == "retry"
        assert pd.migration_confirm_outcome({"status": "error", "code": 500}) == "retry"
        assert pd.migration_confirm_outcome(None) == "retry"
