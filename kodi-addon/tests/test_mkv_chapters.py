"""Chapitres lus dans un fichier MKV (lib/mkv_chapters.py), sur des fichiers fabriqués ici."""

from __future__ import annotations

import io

import mkv_chapters as mk


def _size(length: int) -> bytes:
    return bytes([0x01]) + length.to_bytes(7, "big")  # taille sur 8 octets (marqueur 0x01)


def el(ident: int, payload: bytes) -> bytes:
    raw = ident.to_bytes((ident.bit_length() + 7) // 8, "big")
    return raw + _size(len(payload)) + payload


def uint(ident: int, value: int) -> bytes:
    return el(ident, value.to_bytes(8, "big"))


def atom(start_s: float, name: str, hidden: bool = False) -> bytes:
    payload = uint(mk.TIME_START, int(start_s * 1e9))
    if hidden:
        payload += uint(mk.HIDDEN, 1)
    payload += el(mk.DISPLAY, el(mk.STRING, name.encode()) + el(0x437C, b"eng"))
    return el(mk.ATOM, payload)


CHAPTERS = el(
    mk.CHAPTERS,
    el(
        mk.EDITION,
        uint(mk.EDITION_DEFAULT, 1)
        + atom(0, "Previously on")
        + atom(10, "Opening")
        + atom(30, "Episode")
        + atom(50, "Caché", hidden=True)
        + atom(70, "End Credits"),
    ),
)
HEADER = el(mk.EBML, el(0x4282, b"matroska"))
INFO = el(0x1549A966, uint(0x2AD7B1, 1000000))
CLUSTER = el(mk.CLUSTER, b"\x00" * 64)
EXPECTED = [(0.0, "Previously on"), (10.0, "Opening"), (30.0, "Episode"), (70.0, "End Credits")]


def test_chapters_before_the_clusters():
    data = HEADER + el(mk.SEGMENT, INFO + CHAPTERS + CLUSTER)
    assert mk.read_chapters(io.BytesIO(data)) == EXPECTED


def test_chapters_at_the_end_found_through_the_seek_head():
    def segment(chapters_pos: int) -> bytes:
        seek = el(
            mk.SEEK,
            el(mk.SEEK_ID, mk.CHAPTERS.to_bytes(4, "big")) + uint(mk.SEEK_POSITION, chapters_pos),
        )
        return el(mk.SEEK_HEAD, seek) + INFO + CLUSTER

    # Position de la table dans le segment : taille de ce qui la précède
    body = segment(0)
    body = segment(len(body))
    data = HEADER + el(mk.SEGMENT, body + CHAPTERS)
    assert mk.read_chapters(io.BytesIO(data)) == EXPECTED


def test_no_chapters_or_not_a_mkv():
    assert mk.read_chapters(io.BytesIO(HEADER + el(mk.SEGMENT, INFO + CLUSTER))) == []
    assert mk.read_chapters(io.BytesIO(b"\x00\x00\x00\x18ftypisom")) == []  # un MP4
    assert mk.read_chapters(io.BytesIO(b"")) == []
    assert mk.read_chapters(io.BytesIO(HEADER + b"\x18\x53")) == []  # fichier tronqué


def test_block_reader_reads_through_blocks():
    data = HEADER + el(mk.SEGMENT, INFO + CHAPTERS + CLUSTER)
    calls = []

    def read_block(offset: int, size: int) -> bytes:
        calls.append(offset)
        return data[offset : offset + size]

    reader = mk.BlockReader(read_block)
    assert mk.read_chapters(reader) == EXPECTED
    assert calls == [0]  # un seul bloc de 64 Ko pour tout l'en-tête
    reader.seek(len(data) - 3)
    assert reader.read(10) == data[-3:]  # fin de fichier : on rend ce qu'il y a


def test_readable_paths():
    assert mk.readable("/storage/emulated/0/Movies/Film.mkv")
    assert mk.readable("smb://nas/media/Séries/S01E01.MKV")
    assert mk.readable("nfs://nas/media/a.webm")
    assert not mk.readable("smb://nas/media/Film.mp4")  # pas un MKV
    assert not mk.readable("plugin://plugin.video.x/play.mkv")  # un flux
    assert not mk.readable("http://host/a.mkv")
    assert not mk.readable("")
