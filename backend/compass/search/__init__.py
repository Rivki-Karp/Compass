"""Fuzzy search over occupations and vehicles (catalog, aliases, Tax Authority dataset)."""

from compass.search.normalize import normalize
from compass.search.search import (
    Candidate,
    Searcher,
    SearchResult,
    load_aliases,
    load_manufacturer_aliases,
)

__all__ = [
    "Candidate",
    "SearchResult",
    "Searcher",
    "load_aliases",
    "load_manufacturer_aliases",
    "normalize",
]
