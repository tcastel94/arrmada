# -*- coding: utf-8 -*-
"""Chapitres d'un fichier MKV lus directement dans le fichier (1.17.0).

Pourquoi : sous Kodi 20, l'information « chapitre en cours » du lecteur
(Player.Chapter / ChapterName) ne bouge pas pendant une lecture normale —
elle n'est mise à jour qu'après un saut (vérifié sur le banc : toujours
« chapitre 1 » à 0:44 alors que le 2e commence à 0:10). Et l'API de Kodi ne
donne pas la liste des chapitres. On la lit donc nous-mêmes : nom et heure
de début de chaque chapitre, puis on compare à la position de lecture.

Le MKV est un format EBML (une sorte de XML binaire) : chaque élément est
« identifiant + taille + contenu ». On ne lit que l'en-tête du fichier
(quelques Ko, même sur un partage SMB) : la table des chapitres est rangée
avant les images, ou bien indiquée par l'index du début (SeekHead).

Logique pure, sans Kodi (testée en CI) : `read_chapters` prend n'importe
quel objet fichier binaire (read / seek).
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

EBML = 0x1A45DFA3
SEGMENT = 0x18538067
SEEK_HEAD = 0x114D9B74
SEEK = 0x4DBB
SEEK_ID = 0x53AB
SEEK_POSITION = 0x53AC
CHAPTERS = 0x1043A770
EDITION = 0x45B9
EDITION_DEFAULT = 0x45DB
ATOM = 0xB6
TIME_START = 0x91
HIDDEN = 0x98
DISPLAY = 0x80
STRING = 0x85
CLUSTER = 0x1F43B675

MAX_SCAN = 4 * 1024 * 1024  # on ne lit jamais plus de 4 Mo du début du fichier
MAX_CHAPTERS = 200
UNKNOWN = -1  # taille « inconnue » (segment écrit en flux)


EXTENSIONS = (".mkv", ".mk3d", ".webm")
SCHEMES = ("smb://", "nfs://", "file://")


def readable(path: str) -> bool:
    """Un MKV local ou sur un partage : chemin /storage/…, smb://, nfs://.

    Les flux (plugin://, http://…) et les autres formats ne sont pas lus :
    pour eux, on garde l'information de chapitre donnée par Kodi.
    """
    text = str(path or "").lower()
    if not text.endswith(EXTENSIONS):
        return False
    return "://" not in text or text.startswith(SCHEMES)


class BlockReader:
    """Lecture par blocs de 64 Ko gardés en mémoire.

    Le décodage lit des morceaux de 1 à 8 octets : sur un partage SMB, chaque
    lecture serait un aller-retour réseau. On lit donc par gros blocs (en
    pratique 1 ou 2 pour toute la table des chapitres). `read_block(début,
    taille)` rend les octets du fichier (xbmcvfs.File côté Kodi).
    """

    BLOCK = 65536

    def __init__(self, read_block) -> None:
        self._read_block = read_block
        self._blocks: dict = {}
        self._pos = 0

    def seek(self, pos: int) -> None:
        self._pos = pos

    def read(self, count: int) -> bytes:
        out = b""
        while count > 0:
            number, offset = divmod(self._pos, self.BLOCK)
            if number not in self._blocks:
                block = self._read_block(number * self.BLOCK, self.BLOCK)
                self._blocks[number] = bytes(block or b"")
            chunk = self._blocks[number][offset : offset + count]
            if not chunk:
                break
            out += chunk
            self._pos += len(chunk)
            count -= len(chunk)
        return out


class _Reader:
    def __init__(self, handle: Any) -> None:
        self.handle = handle
        self.pos = 0

    def seek(self, pos: int) -> None:
        self.handle.seek(pos)
        self.pos = pos

    def read(self, count: int) -> bytes:
        data = bytes(self.handle.read(count) or b"")
        self.pos += len(data)
        return data

    def element_id(self) -> Optional[int]:
        first = self.read(1)
        if not first:
            return None
        length = _vint_length(first[0])
        if length is None or length > 4:
            return None
        rest = self.read(length - 1)
        if len(rest) != length - 1:
            return None
        return int.from_bytes(first + rest, "big")

    def size(self) -> Optional[int]:
        first = self.read(1)
        if not first:
            return None
        length = _vint_length(first[0])
        if length is None:
            return None
        rest = self.read(length - 1)
        if len(rest) != length - 1:
            return None
        value = first[0] & (0xFF >> length)
        for byte in rest:
            value = (value << 8) | byte
        if value == (1 << (7 * length)) - 1:
            return UNKNOWN
        return value

    def header(self) -> Optional[Tuple[int, int, int]]:
        """(identifiant, taille, début du contenu) de l'élément suivant."""
        ident = self.element_id()
        size = self.size() if ident is not None else None
        if ident is None or size is None:
            return None
        return ident, size, self.pos


def _vint_length(byte: int) -> Optional[int]:
    for length in range(1, 9):
        if byte & (0x80 >> (length - 1)):
            return length
    return None


def _children(reader: _Reader, start: int, end: int):
    """Éléments enfants entre `start` et `end` : (identifiant, taille, début)."""
    reader.seek(start)
    while reader.pos < end:
        head = reader.header()
        if head is None:
            return
        ident, size, data = head
        if size == UNKNOWN:
            return  # un enfant sans taille : on ne sait pas où il finit
        yield ident, size, data
        reader.seek(data + size)


def _uint(reader: _Reader, data: int, size: int) -> int:
    reader.seek(data)
    return int.from_bytes(reader.read(min(size, 8)), "big") if size else 0


def _text(reader: _Reader, data: int, size: int) -> str:
    reader.seek(data)
    return reader.read(min(size, 512)).decode("utf-8", "replace").rstrip("\x00").strip()


def _atom(reader: _Reader, data: int, size: int) -> Optional[Tuple[float, str]]:
    start_ns, name, hidden = None, "", False
    for ident, child_size, child in list(_children(reader, data, data + size)):
        if ident == TIME_START:
            start_ns = _uint(reader, child, child_size)
        elif ident == HIDDEN:
            hidden = bool(_uint(reader, child, child_size))
        elif ident == DISPLAY and not name:
            for sub, sub_size, sub_data in list(_children(reader, child, child + child_size)):
                if sub == STRING:
                    name = _text(reader, sub_data, sub_size)
                    break
    if start_ns is None or hidden:
        return None
    return start_ns / 1e9, name


def _chapters(reader: _Reader, data: int, size: int) -> List[Tuple[float, str]]:
    editions = []
    for ident, edition_size, edition in list(_children(reader, data, data + size)):
        if ident != EDITION:
            continue
        default, atoms = False, []
        for sub, sub_size, sub_data in list(_children(reader, edition, edition + edition_size)):
            if sub == EDITION_DEFAULT:
                default = bool(_uint(reader, sub_data, sub_size))
            elif sub == ATOM and len(atoms) < MAX_CHAPTERS:
                atom = _atom(reader, sub_data, sub_size)
                if atom:
                    atoms.append(atom)
        editions.append((default, atoms))
    if not editions:
        return []
    chosen = next((atoms for default, atoms in editions if default), editions[0][1])
    return sorted(chosen)


def read_chapters(handle: Any) -> List[Tuple[float, str]]:
    """[(début en secondes, nom), …] du MKV ; [] sans chapitres ou fichier illisible."""
    reader = _Reader(handle)
    try:
        head = reader.header()
        if head is None or head[0] != EBML:
            return []
        reader.seek(head[2] + head[1])
        segment = reader.header()
        if segment is None or segment[0] != SEGMENT:
            return []
        start = segment[2]
        end = start + segment[1] if segment[1] != UNKNOWN else start + MAX_SCAN
        chapters_at = None
        reader.seek(start)
        while reader.pos < min(end, start + MAX_SCAN):
            element = reader.header()
            if element is None:
                break
            ident, size, data = element
            if ident == CHAPTERS:
                return _chapters(reader, data, size)
            if ident == SEEK_HEAD:
                chapters_at = _seek_target(reader, data, size, start)
            if ident == CLUSTER or size == UNKNOWN:
                break  # les images commencent : la table, si elle existe, est plus loin
            reader.seek(data + size)
        if chapters_at is not None:
            reader.seek(chapters_at)
            element = reader.header()
            if element and element[0] == CHAPTERS:
                return _chapters(reader, element[2], element[1])
    except (OSError, ValueError, OverflowError):
        return []
    return []


def _seek_target(reader: _Reader, data: int, size: int, segment_start: int) -> Optional[int]:
    """Position de la table des chapitres d'après l'index du début (SeekHead)."""
    for ident, seek_size, seek in list(_children(reader, data, data + size)):
        if ident != SEEK:
            continue
        target_id = target_pos = None
        for sub, sub_size, sub_data in list(_children(reader, seek, seek + seek_size)):
            if sub == SEEK_ID:
                target_id = _uint(reader, sub_data, sub_size)
            elif sub == SEEK_POSITION:
                target_pos = _uint(reader, sub_data, sub_size)
        if target_id == CHAPTERS and target_pos is not None:
            return segment_start + target_pos
    return None
