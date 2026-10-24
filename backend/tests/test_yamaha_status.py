"""État de l'ampli exposé à la TV (menu pause : voix, mode nuit)."""

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
