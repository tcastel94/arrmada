"""Panneau ArrMada pendant le film (lib/player_data.py)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import player_data as pd

AUDIO = [
    {
        "index": 0,
        "language": "eng",
        "codec": "truehd",
        "channels": 8,
        "name": "",
        "isoriginal": True,
    },
    {"index": 1, "language": "fre", "codec": "eac3", "channels": 6, "name": "VFF"},
    {"index": 2, "language": "fre", "codec": "ac3", "channels": 2, "name": "", "isimpaired": True},
]
SUBS = [
    {"index": 0, "language": "fre", "name": "", "isforced": True},
    {"index": 1, "language": "fre", "name": "SDH", "isimpaired": True},
    {"index": 2, "language": "und", "name": ""},
]


def test_labels():
    assert pd.language_name("fre") == "Français" and pd.language_name("FR") == "Français"
    assert (
        pd.language_name("und") == "Langue inconnue" and pd.language_name("") == "Langue inconnue"
    )
    assert pd.language_name("tha") == "THA"
    assert pd.codec_label("dtshd_ma") == "DTS-HD MA" and pd.codec_label("pcm_s24le") == "PCM"
    assert pd.channels_label(8) == "7.1" and pd.channels_label(2) == "Stéréo"
    assert pd.channels_label(0) == ""


def test_audio_options():
    options = pd.audio_options(AUDIO, current=1)
    assert [(o["label"], o["label2"]) for o in options] == [
        ("Anglais", "Dolby TrueHD 7.1 · VO"),
        ("Français", "Dolby Digital Plus 5.1 · VFF"),
        ("Français", "Dolby Digital Stéréo · Audiodescription"),
    ]
    assert [o["selected"] for o in options] == [False, True, False]
    assert options[1]["op"] == "audio" and options[1]["value"] == 1
    assert pd.current_audio_summary(options) == "Français · Dolby Digital Plus 5.1"


def test_subtitle_options():
    options = pd.subtitle_options(SUBS, current=1, enabled=True)
    assert [o["op"] for o in options] == [
        "subtitle_off", "subtitle", "subtitle", "subtitle", "bazarr_search", "bazarr_sync",
    ]  # fmt: skip
    assert options[1]["label2"] == "Forcés" and options[2]["label2"] == "Malentendants · SDH"
    assert options[2]["selected"] and not options[0]["selected"]
    assert options[4]["label"] == "Chercher en français avec Bazarr"
    assert pd.current_subtitle_summary(options) == "Français · Malentendants · SDH"
    off = pd.subtitle_options(SUBS, current=1, enabled=False)
    assert off[0]["selected"] and pd.current_subtitle_summary(off) == "Désactivés"
    # Fichier sans sous-titres : Désactivés + actions Bazarr
    assert [o["op"] for o in pd.subtitle_options([], None, False, "en")] == [
        "subtitle_off", "bazarr_search", "bazarr_sync",
    ]  # fmt: skip


def test_amp_and_playback():
    model = {
        "configured": True, "online": True, "volume": "48 %", "db": "−32,0 dB", "mute": False,
        "presets": [{"room": "salon", "name": "Salon"}, {"room": "cinema", "name": "Cinéma"}],
    }  # fmt: skip
    amp = pd.amp_options(model, room="cinema")
    assert [o["label"] for o in amp] == [
        "Volume −", "Volume +", "Couper le son", "Préréglage « Salon »", "Préréglage « Cinéma »",
    ]  # fmt: skip
    assert amp[0]["label2"] == "48 % · −32,0 dB" and amp[0]["value"] == -pd.VOLUME_STEP
    assert amp[4]["label2"] == "Cette pièce"
    assert (
        pd.amp_options(dict(model, online=False)) == []
    )  # ampli éteint du réseau : pas de section

    nxt = {"season": 1, "episode": 6, "title": "Hide and Seek"}
    playback = pd.playback_options(nxt, queued_after=3, chapters=12, position=600)
    assert [o["op"] for o in playback] == ["next", "stop_after", "chapter", "chapter", "restart"]
    assert playback[0]["label2"] == "S01E06 · Hide and Seek"
    assert playback[1]["label2"] == "3 épisodes en file"
    # Film sans chapitres, tout début : rien à proposer
    assert pd.playback_options(None, 0, 1, 20) == []


def test_sections_skip_empty():
    audio = pd.audio_options(AUDIO, 0)
    subs = pd.subtitle_options([], None, False)
    keys = [s["key"] for s in pd.sections(audio, subs, [], [], "")]
    assert keys == ["audio", "subtitles"]  # pas d'ampli, rien à faire côté lecture
    first = pd.sections(audio, subs, [], [])[0]
    assert first == {"key": "audio", "label": "Audio", "label2": "Anglais · Dolby TrueHD 7.1"}


def test_new_subtitle_file():
    folder, base = pd.split_path("smb://nas/films/Dune (2021)/Dune.2021.2160p.mkv")
    assert folder == "smb://nas/films/Dune (2021)/" and base == "Dune.2021.2160p"
    listing = ["Dune.2021.2160p.mkv", "Dune.2021.2160p.en.srt", "poster.jpg", "Autre.fr.srt"]
    before = pd.subtitle_files(listing, base)
    assert before == ["Dune.2021.2160p.en.srt"]
    after = pd.subtitle_files(
        listing + ["Dune.2021.2160p.fr.forced.srt", "Dune.2021.2160p.fr.srt"], base
    )
    assert pd.new_subtitle(before, after, "fr") == "Dune.2021.2160p.fr.srt"  # pas les forcés
    assert pd.new_subtitle(after, after, "fr") == ""
    assert pd.language_subtitle(after, "fr") == "Dune.2021.2160p.fr.srt"
    assert pd.language_subtitle(after, "de") == ""


def test_keymap():
    xml = pd.keymap_xml()
    root = ET.fromstring(xml.split("\n", 1)[1])  # sans la déclaration XML
    keys = root.find("FullscreenVideo")
    assert keys.find("keyboard/return").get("mod") == "longpress"
    assert "action=player" in keys.find("remote/select").text
    assert pd.keymap_change(True, None) == "write"
    assert pd.keymap_change(True, xml) == ""
    assert pd.keymap_change(True, "ancien contenu") == "write"
    assert pd.keymap_change(False, xml) == "remove"
    assert pd.keymap_change(False, None) == ""


def test_clean_title():
    assert pd.clean_title("Concert.Zenith.2025.mkv") == "Concert Zenith 2025"
    assert pd.clean_title("Dune : Deuxième partie") == "Dune : Deuxième partie"
    assert pd.clean_title("") == ""


def test_external_subtitle_name():
    external = {"index": 3, "language": "fre", "name": "(External)"}
    assert pd.subtitle_label(external) == {"label": "Français", "label2": "Fichier externe"}


def test_auto_subtitles_decision():
    assert pd.language_code("fre") == pd.language_code("fra") == pd.language_code("fr") == "fr"
    assert pd.language_code("French") == "" and pd.language_code("Français") == "fr"
    assert pd.language_code("und") == "" and pd.language_code("") == ""
    english = {"language": "eng"}
    french = {"language": "fre"}
    # VO sans sous-titres français : on cherche
    assert pd.needs_subtitles(english, [], "fr")
    assert pd.needs_subtitles(english, [{"language": "eng"}], "fr")
    # Seulement des forcés : ça ne suffit pas pour un film en VO
    assert pd.needs_subtitles(english, [{"language": "fre", "isforced": True}], "fr")
    # Déjà des sous-titres complets en français, ou film en VF : rien à faire
    assert not pd.needs_subtitles(english, [{"language": "fra"}], "fr")
    assert not pd.needs_subtitles(french, [], "fr")
    # Langue de l'audio inconnue : on ne devine pas
    assert not pd.needs_subtitles({"language": "und"}, [], "fr")
    assert not pd.needs_subtitles(None, [], "fr")
