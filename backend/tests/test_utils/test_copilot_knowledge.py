"""Copilote : masquage des secrets et recherche dans la documentation d'ArrMada."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings
from app.services.copilot import knowledge
from app.services.copilot.redaction import MASK, Redactor

# ── Masquage des secrets ────────────────────────────────────────


def test_known_secret_is_masked_wherever_it_appears() -> None:
    redactor = Redactor({"0123456789abcdef0123456789abcdef"})
    line = "GET /api/v3/movie?foo=0123456789abcdef0123456789abcdef → 200"
    assert redactor.text(line) == f"GET /api/v3/movie?foo={MASK} → 200"


def test_short_known_secret_is_not_replaced_blindly() -> None:
    # « 8989 » comme mot de passe ne doit pas masquer le port de Sonarr partout
    redactor = Redactor({"8989"})
    assert redactor.text("http://sonarr:8989/api") == "http://sonarr:8989/api"


def test_fields_named_like_secrets_are_masked() -> None:
    cleaned = Redactor().data(
        {"apiKey": "abc", "password": "hunter2", "port": 7878, "username": "jeff", "token": ""}
    )
    assert cleaned == {
        "apiKey": MASK,
        "password": MASK,
        "port": 7878,
        "username": "jeff",
        "token": "",  # vide = « non renseigné », une information utile
    }


def test_arr_provider_fields_are_masked() -> None:
    cleaned = Redactor().data(
        {
            "name": "SABnzbd",
            "fields": [
                {"name": "host", "value": "sabnzbd"},
                {"name": "apiKey", "value": "sab-key"},
                {"name": "extra", "value": "s3cret", "privacy": "password"},
            ],
        }
    )
    assert [f["value"] for f in cleaned["fields"]] == ["sabnzbd", MASK, MASK]


def test_secrets_in_free_text_are_masked() -> None:
    redactor = Redactor()
    assert (
        redactor.text("https://indexer.test/api?t=search&apikey=XYZ123&q=dune")
        == f"https://indexer.test/api?t=search&apikey={MASK}&q=dune"
    )
    assert redactor.text("postgresql://arrmada:pg-pass@db:5432/arrmada") == (
        f"postgresql://arrmada:{MASK}@db:5432/arrmada"
    )
    assert redactor.text('"passkey": "abcdef"') == f'"passkey": "{MASK}"'


def test_nested_structures_are_cleaned() -> None:
    cleaned = Redactor({"super-secret-value"}).data(
        {"items": [{"message": "échec avec super-secret-value"}, ("a", {"secret": "x"})]}
    )
    assert cleaned == {"items": [{"message": f"échec avec {MASK}"}, ["a", {"secret": MASK}]]}


# ── Documentation ───────────────────────────────────────────────


@pytest.fixture
def docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un petit jeu de documents dans un dossier temporaire."""
    adr = tmp_path / "adr"
    adr.mkdir()
    (adr / "012-qualite-de-lecture.md").write_text(
        "# ADR-012 : Qualité de lecture\n\n"
        "## Contexte\n\nLa Shield ne décode pas l'AV1.\n\n"
        "## Décision\n\n### Bascule en 1080p\n\nConversion par Jellyfin quand le fichier "
        "n'est pas décodable.\n\n```bash\n# pas un titre\n```\n",
        encoding="utf-8",
    )
    (adr / "010-application-trash-guides.md").write_text(
        "# ADR-010 : Application des TRaSH Guides\n\n## Décision\n\nProfils et formats "
        "appliqués depuis l'assistant.\n",
        encoding="utf-8",
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Sous-titres\n\n"
        + "Bazarr range les fichiers sans code de langue. " * 900
        + "\n\n### Autre\n\nRien.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "COPILOT_KNOWLEDGE_DIR", str(tmp_path))
    knowledge.load(force=True)
    yield tmp_path
    monkeypatch.setattr(knowledge, "_documents", None)


def test_catalog_lists_documents_with_their_titles(docs: Path) -> None:
    assert knowledge.catalog() == [
        {"id": "adr-010", "title": "ADR-010 : Application des TRaSH Guides", "kind": "adr"},
        {"id": "adr-012", "title": "ADR-012 : Qualité de lecture", "kind": "adr"},
        {"id": "changelog", "title": "Changelog", "kind": "changelog"},
    ]


def test_search_ignores_accents_and_ranks_the_matching_section_first(docs: Path) -> None:
    results = knowledge.search("qualite bascule 1080p")
    assert results[0]["doc"] == "adr-012"
    assert results[0]["section"] == "ADR-012 : Qualité de lecture › Décision › Bascule en 1080p"
    assert "Jellyfin" in results[0]["excerpt"]


def test_search_without_usable_word_returns_nothing(docs: Path) -> None:
    assert knowledge.search("?? !") == []


def test_code_fences_are_not_taken_for_headings(docs: Path) -> None:
    headings = [s.heading for s in knowledge.load()["adr-012"].sections]
    assert not any("pas un titre" in heading for heading in headings)


def test_read_a_single_section(docs: Path) -> None:
    result = knowledge.read("ADR-012", section="contexte")
    assert result["sections"] == ["ADR-012 : Qualité de lecture › Contexte"]
    assert "AV1" in result["text"]


def test_read_a_long_document_returns_its_outline(docs: Path) -> None:
    result = knowledge.read("changelog")
    assert result["truncated"] is True
    assert len(result["text"]) == knowledge.MAX_READ_CHARS
    assert "Changelog › [Unreleased] › Autre" in result["sections"]


def test_read_unknown_document_or_section_says_what_exists(docs: Path) -> None:
    assert knowledge.read("adr-999")["available"] == ["adr-010", "adr-012", "changelog"]
    assert "sections" in knowledge.read("adr-012", section="introuvable")
