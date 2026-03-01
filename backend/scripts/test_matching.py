"""Quick unit test for the article-stripping matching logic."""
import re

_ARTICLES = frozenset({
    "of", "the", "and", "a", "an", "in", "on", "at", "to", "for",
    "le", "la", "les", "de", "du", "des",
})

tests = [
    ("godfather.of.harlem.s03e01.1080p.x265-elite", "godfatherharlem"),
    ("the.expanse.s06e01.1080p", "expanse"),
    ("game.of.thrones.s08e06.1080p", "gamethrones"),
    ("la.casa.de.papel.s05e10.1080p", "casapapel"),
]

for match_name, sonarr_clean in tests:
    title_part = re.split(r"\.s\d{2}", match_name, flags=re.IGNORECASE)[0]
    download_words = [w for w in title_part.split(".") if w.lower() not in _ARTICLES]
    download_clean = "".join(download_words).lower()
    
    matched = download_clean in sonarr_clean or sonarr_clean in download_clean
    status = "OK" if matched else "FAIL"
    print(f"[{status}] '{match_name}' => download_clean='{download_clean}' vs sonarr='{sonarr_clean}' => {matched}")
