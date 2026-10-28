"""État de l'ampli exposé à la TV (menu pause : voix, mode nuit)."""

from types import SimpleNamespace

import pytest

from app.services.yamaha import zone_status


def test_zone_status_with_dialogue_and_drc() -> None:
    st = {
        "power": "on",
        "volume": 65,
        "max_volume": 161,
        "mute": False,
        "input": "hdmi1",
        "actual_volume": {"mode": "db", "value": -42.5, "unit": "dB"},
        "sound_program": "surr_decoder",
        "dialogue_lift": 2,
        "dialogue_level": 1,
        "adaptive_drc": True,
        "enhancer": False,
        "subwoofer_volume": -2,
    }
    out = zone_status(st)
    assert out["volume_pct"] == 40
    assert out["actual_db"] == -42.5
    assert (out["dialog_lift"], out["dialog_level"], out["adaptive_drc"]) == (2, 1, True)
    assert out["enhancer"] is False
    assert out["extra_bass"] is None  # absent de cet ampli
    assert out["subwoofer_volume"] == -2


def test_zone_status_without_extras() -> None:
    out = zone_status({"power": "standby", "volume": 0})
    assert out["dialog_level"] is None
    assert out["adaptive_drc"] is None
    assert out["mute"] is False


def test_default_profiles_describe_speakers() -> None:
    from app.services.yamaha import DEFAULT_PROFILES

    assert DEFAULT_PROFILES["salon"]["speakers"] == "5.1"
    assert DEFAULT_PROFILES["cinema"]["speakers"] == "7.2.2"


# ── Télécommande de la TV → ampli (touches volume / muet) ─────────────


class _FakeAvr:
    """Ampli YXC simulé : retient les appels, répond à getStatus."""

    def __init__(self, mute: bool = False) -> None:
        self.calls: list[str] = []
        self.status = {"power": "on", "volume": 65, "max_volume": 161, "mute": mute,
                       "actual_volume": {"value": -38.5}}  # fmt: skip

    async def get(self, base: str, path: str, *, timeout: float = 4.0) -> dict:
        self.calls.append(path)
        if path.endswith("/setVolume?volume=up&step=4"):
            self.status["volume"] += 4
        if "setMute?enable=" in path:
            self.status["mute"] = path.endswith("true")
        return dict(self.status)


@pytest.fixture
def avr(monkeypatch: pytest.MonkeyPatch) -> _FakeAvr:
    from app.services import yamaha

    fake = _FakeAvr()

    async def pick(_db: object, _service_id: object) -> SimpleNamespace:
        return SimpleNamespace(url="http://192.168.1.50", id=1)

    monkeypatch.setattr(yamaha, "_get", fake.get)
    monkeypatch.setattr(yamaha, "_pick", pick)
    return fake


async def test_volume_step_returns_new_level(avr: _FakeAvr) -> None:
    from app.services.yamaha import control

    out = await control(None, "volume_step", 4)  # type: ignore[arg-type]
    assert out == {
        "status": "ok",
        "action": "volume_step",
        "volume_pct": 43,
        "mute": False,
        "actual_db": -38.5,
    }
    assert avr.calls[0] == "/main/setVolume?volume=up&step=4"


async def test_mute_toggle_reads_then_inverts(avr: _FakeAvr) -> None:
    from app.services.yamaha import control

    out = await control(None, "mute", "toggle")  # type: ignore[arg-type]
    assert avr.calls[:2] == ["/main/getStatus", "/main/setMute?enable=true"]
    assert out["mute"] is True
    out = await control(None, "mute", "toggle")  # type: ignore[arg-type]
    assert avr.calls[-2] == "/main/setMute?enable=false"
    assert out["mute"] is False


async def test_explicit_mute_still_works_and_other_actions_unchanged(avr: _FakeAvr) -> None:
    from app.services.yamaha import control

    await control(None, "mute", True)  # type: ignore[arg-type]
    assert avr.calls == ["/main/setMute?enable=true", "/main/getStatus"]
    out = await control(None, "sound_program", "straight")  # type: ignore[arg-type]
    assert out == {"status": "ok", "action": "sound_program"}
