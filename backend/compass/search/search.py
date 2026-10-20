"""Fuzzy lookup of occupations and vehicles (Hebrew / English, typos).

Score = mean of rapidfuzz WRatio and plain ratio on normalized text. WRatio alone rewards a
candidate that matches only *part* of the query: "קורולה קורס" (a typo for COROLLA CROSS) scores
90.9 for COROLLA CROSS and 90.0 for COROLLA, because "קורולה" is a substring. Plain ratio
penalizes the length mismatch (70.6), so the blend separates them (90.9 vs 80.3).

`confident` = top score >= CONFIDENT_SCORE, lead over the next *different* candidate >=
CONFIDENT_LEAD, and the top match is not strictly extended by another car's name. Callers must
never auto-pick when not confident.

The extension rule: "קורולה" matches COROLLA exactly, but COROLLA CROSS's name extends it
("קורולה" + "קרוס"). A user who types just "קורולה" may well mean the Corolla Cross, and a wrong
pick silently changes the value of use (4,120 vs 4,070), so we ask instead of guessing.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict
from rapidfuzz import fuzz

from compass.config import ALIASES_YAML, VEHICLES_DB
from compass.data.catalog import CatalogCar
from compass.data.occupations import Occupation
from compass.data.vehicles import VehicleRecord, commercial_names, find_by_names
from compass.search.normalize import normalize

CONFIDENT_SCORE = 85.0
CONFIDENT_LEAD = 10.0
MIN_SCORE = 70.0  # below this a candidate is not shown at all
MAX_CANDIDATES = 5
_EXTRA_TOKEN_MATCH = 80.0  # the query "mentions" an extension token at this ratio

# search_catalog (a list to pick from, never a pick): how a partial name, the manufacturer and
# a transliteration score next to a full-name match.
CATALOG_CHOICES = 6
PARTIAL_MIN_LENGTH = 3
PARTIAL_MIN_SCORE = 90.0  # below this a partial match is noise ("קיה" inside "אוקטביה")
PARTIAL_WEIGHT = 0.9  # "קורולה" inside "קורולה קרוס": listed, below the exact match
MAKER_SCORE = 80.0  # the manufacturer named: every car of it, below a name match
SKELETON_WEIGHT = 0.85

_HEBREW = re.compile(r"[א-ת]")
# Hebrew letters -> Latin consonants, and Latin spelling -> the same consonants, so "קודיאק" and
# "kodiaq" both read "kdk". Vowel letters (א ה ו י ע) drop on both sides, as vowels do.
_HEBREW_SOUNDS = str.maketrans(
    {
        "ב": "b", "ג": "g", "ד": "d", "ז": "z", "ח": "k", "ט": "t", "כ": "k", "ל": "l",
        "מ": "m", "נ": "n", "ס": "s", "פ": "p", "צ": "z", "ק": "k", "ר": "r", "ש": "s",
        "ת": "t", "א": "", "ה": "", "ו": "", "י": "", "ע": "",
    }
)  # fmt: skip
_LATIN_SOUNDS = (
    ("ph", "p"), ("ch", "k"), ("ck", "k"), ("sh", "s"), ("ts", "z"), ("tz", "z"),
    ("c", "k"), ("q", "k"), ("x", "ks"), ("f", "p"), ("v", "b"), ("w", "b"), ("j", "g"),
)  # fmt: skip


def latin_skeleton(text: str) -> str:
    """The consonants of normalized text, in one Latin spelling for Hebrew and English alike;
    digits kept, doubled letters and spaces dropped."""
    for spelling, sound in _LATIN_SOUNDS:  # Latin spelling first: the Hebrew is already sounds
        text = text.replace(spelling, sound)
    text = text.translate(_HEBREW_SOUNDS)
    text = re.sub(r"[aeiouyh\s]", "", text)
    return re.sub(r"(.)\1+", r"\1", text)


Source = Literal["catalog", "occupations", "tax_authority"]


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str  # catalog car id, occupation title, or tax-authority full key
    label: str
    score: float
    source: Source
    in_catalog: bool
    matched: str  # the normalized name or alias that produced the score


class SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str
    candidates: tuple[Candidate, ...]
    confident: bool
    truncated: bool = False  # more than MAX_CANDIDATES matched

    @property
    def best(self) -> Candidate | None:
        """The pick, only when confident."""
        return self.candidates[0] if self.confident else None


def score(query: str, candidate: str) -> float:
    """Blend of WRatio and ratio on already-normalized strings."""
    return (fuzz.WRatio(query, candidate) + fuzz.ratio(query, candidate)) / 2


MANUFACTURERS_KEY = "manufacturers"  # aliases.yaml's section of brand spellings


def load_aliases(path: Path = ALIASES_YAML) -> dict[str, tuple[str, ...]]:
    """The car aliases: catalog commercial_name -> aliases."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        str(name): tuple(str(alias) for alias in aliases)
        for name, aliases in data.items()
        if name != MANUFACTURERS_KEY
    }


def load_manufacturer_aliases(path: Path = ALIASES_YAML) -> dict[str, tuple[str, ...]]:
    """The manufacturer spellings: the start of a catalog manufacturer_name -> spellings."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        str(maker): tuple(str(alias) for alias in aliases)
        for maker, aliases in (data.get(MANUFACTURERS_KEY) or {}).items()
    }


def tax_authority_key(record: VehicleRecord) -> str:
    """The full official key as an id: tax year-registration year-type-manufacturer-model."""
    return (
        f"{record.tax_year}-{record.registration_year}-{record.vehicle_type_code}-"
        f"{record.manufacturer_code}-{record.model_code}"
    )


@dataclass(frozen=True)
class _Entry:
    id: str
    label: str
    names: tuple[str, ...]  # normalized


def _best(query: str, entries: Iterable[_Entry]) -> list[tuple[float, str, _Entry]]:
    scored = []
    for entry in entries:
        top, matched = max((score(query, name), name) for name in entry.names)
        scored.append((top, matched, entry))
    scored.sort(key=lambda item: -item[0])  # stable: ties keep data order
    return scored


def _confident(scores: list[float]) -> bool:
    if not scores or scores[0] < CONFIDENT_SCORE:
        return False
    return len(scores) == 1 or scores[0] - scores[1] >= CONFIDENT_LEAD


def _extended_by_other(query: str, matched: str, top: _Entry, entries: Iterable[_Entry]) -> bool:
    """Another entry has a name that contains `matched` as a run of whole words plus more words,
    none of which the query mentions."""
    tokens = matched.split()
    query_tokens = query.split()
    for entry in entries:
        if entry.id == top.id:
            continue
        for name in entry.names:
            other = name.split()
            if len(other) <= len(tokens):
                continue
            for start in range(len(other) - len(tokens) + 1):
                if other[start : start + len(tokens)] != tokens:
                    continue
                extra = other[:start] + other[start + len(tokens) :]
                mentioned = any(
                    fuzz.ratio(word, q) >= _EXTRA_TOKEN_MATCH
                    for word in extra
                    for q in query_tokens
                )
                if not mentioned:
                    return True
    return False


class Searcher:
    """Search indexes over the catalog, occupations, aliases and the tax-authority dataset."""

    def __init__(
        self,
        catalog: Mapping[str, CatalogCar],
        occupations: Mapping[str, Occupation],
        aliases: Mapping[str, tuple[str, ...]],
        value_of_use_tax_year: int,
        vehicles_db: Path = VEHICLES_DB,
        manufacturer_aliases: Mapping[str, tuple[str, ...]] | None = None,
    ) -> None:
        by_name = {car.commercial_name: car for car in catalog.values()}
        unknown = sorted(set(aliases) - set(by_name))
        if unknown:
            raise ValueError(f"aliases.yaml: unknown catalog commercial_name(s) {unknown}")
        makers = {f"{normalize(car.manufacturer_name)} " for car in catalog.values()}
        maker_aliases = {
            normalize(maker): tuple(normalize(a) for a in spellings)
            for maker, spellings in (manufacturer_aliases or {}).items()
        }
        unknown = sorted(k for k in maker_aliases if not any(m.startswith(f"{k} ") for m in makers))
        if unknown:
            raise ValueError(f"aliases.yaml: unknown catalog manufacturer(s) {unknown}")
        self._cars = [
            _Entry(
                id=car.id,
                label=f"{car.commercial_name} {car.registration_year}",
                names=tuple(
                    dict.fromkeys(
                        normalize(n) for n in (car.commercial_name, *aliases.get(name, ()))
                    )
                ),
            )
            for name, car in by_name.items()
        ]
        self._car_years = {car.id: car.registration_year for car in catalog.values()}
        # search_catalog's extra keys per car: the manufacturer's words ("קיה", "טויוטה"; the
        # country is a word too, but no one types it alone), and the consonant skeleton of the
        # commercial name, for a Hebrew transliteration no alias covers.
        self._makers = {
            car.id: tuple(w for w in normalize(car.manufacturer_name).split() if len(w) >= 2)
            for car in catalog.values()
        }
        # ...and the manufacturer's other spellings from aliases.yaml ("kia", "שקודה").
        self._maker_spellings = {
            car.id: tuple(
                spelling
                for key, spellings in maker_aliases.items()
                if f"{normalize(car.manufacturer_name)} ".startswith(f"{key} ")
                for spelling in spellings
            )
            for car in catalog.values()
        }
        self._skeletons = {
            car.id: latin_skeleton(normalize(car.commercial_name)) for car in catalog.values()
        }
        self._occupations = [
            _Entry(id=title, label=title, names=(normalize(title),)) for title in occupations
        ]
        self._tax_year = value_of_use_tax_year
        self._vehicles_db = vehicles_db
        self._tax_names: dict[int | None, dict[str, list[str]]] = {}

    def cars_named_in(self, text: str) -> set[str]:
        """Catalog car ids whose name or alias appears in `text` as whole words (one Hebrew
        prefix letter allowed: "לאטו 3"). Same normalization as the search."""
        words = f" {normalize(text)} "
        return {
            car.id
            for car in self._cars
            if any(
                re.search(rf"(?<=\s)[ובלמהשכ]?{re.escape(name)}(?=\s)", words)
                for name in car.names
                if name
            )
        }

    # --- occupations ------------------------------------------------------------------------

    def search_occupations(self, query: str) -> SearchResult:
        normalized = normalize(query)
        ranked = [r for r in _best(normalized, self._occupations) if r[0] >= MIN_SCORE]
        candidates = tuple(
            Candidate(
                id=entry.id,
                label=entry.label,
                score=round(value, 1),
                source="occupations",
                in_catalog=True,
                matched=matched,
            )
            for value, matched, entry in ranked[:MAX_CANDIDATES]
        )
        return SearchResult(
            query=query,
            candidates=candidates,
            confident=_confident([value for value, _, _ in ranked]),
            truncated=len(ranked) > MAX_CANDIDATES,
        )

    def rank_occupations(self, query: str, limit: int = MAX_CANDIDATES) -> list[str]:
        """The `limit` occupation titles closest to `query`, best first, by the same score as
        search_occupations but with no minimum: a representative chooses among them, so a query
        no title matches well ("מפתח AI") still gets its nearest titles. lookup_occupation's
        candidates (MIN_SCORE and up) always come first."""
        return [entry.id for _, _, entry in _best(normalize(query), self._occupations)[:limit]]

    # --- vehicles ---------------------------------------------------------------------------

    def search_vehicles(self, query: str, registration_year: int | None = None) -> SearchResult:
        """Catalog first; the tax-authority dataset only if no catalog car scores MIN_SCORE."""
        normalized = normalize(query)
        cars = [
            e
            for e in self._cars
            if registration_year is None or self._car_years[e.id] == registration_year
        ]
        ranked = [r for r in _best(normalized, cars) if r[0] >= MIN_SCORE]
        if ranked:
            value, matched, top = ranked[0]
            confident = _confident([v for v, _, _ in ranked]) and not _extended_by_other(
                normalized, matched, top, cars
            )
            candidates = tuple(
                Candidate(
                    id=entry.id,
                    label=entry.label,
                    score=round(v, 1),
                    source="catalog",
                    in_catalog=True,
                    matched=m,
                )
                for v, m, entry in ranked[:MAX_CANDIDATES]
            )
            return SearchResult(
                query=query,
                candidates=candidates,
                confident=confident,
                truncated=len(ranked) > MAX_CANDIDATES,
            )
        return self._search_tax_authority(query, normalized, registration_year)

    def search_catalog(self, query: str, limit: int = CATALOG_CHOICES) -> list[Candidate]:
        """The catalog cars an employee might mean by `query`, best first, for a list to pick
        from (never a pick): every registration year, and besides search_vehicles' score on the
        names and aliases, a partial name ("קורולה" also lists COROLLA CROSS), the manufacturer
        ("קיה", or a spelling from aliases.yaml such as "kia": every Kia) and a Hebrew
        transliteration of the commercial name ("קודיאק" would find KODIAQ). Empty when nothing
        scores MIN_SCORE."""
        normalized = normalize(query)
        if not normalized:
            return []
        words = normalized.split()
        skeleton = latin_skeleton(normalized) if _HEBREW.search(normalized) else ""
        scored: list[tuple[float, str, _Entry]] = []
        for entry in self._cars:
            best, matched = max((score(normalized, name), name) for name in entry.names)
            if len(normalized) >= PARTIAL_MIN_LENGTH:
                partial, name = max((fuzz.partial_ratio(normalized, n), n) for n in entry.names)
                if partial >= PARTIAL_MIN_SCORE and partial * PARTIAL_WEIGHT > best:
                    best, matched = partial * PARTIAL_WEIGHT, name
            maker = self._makers[entry.id]
            named = any(fuzz.ratio(w, m) >= CONFIDENT_SCORE for w in words for m in maker) or any(
                f" {s} " in f" {normalized} "
                if " " in s
                else any(fuzz.ratio(w, s) >= CONFIDENT_SCORE for w in words)
                for s in self._maker_spellings[entry.id]
            )
            if named and best < MAKER_SCORE:
                best, matched = MAKER_SCORE, " ".join(maker)
            target = self._skeletons[entry.id]
            if len(skeleton) >= PARTIAL_MIN_LENGTH and target:
                sounds = fuzz.ratio(skeleton, target) * SKELETON_WEIGHT
                if sounds > best:
                    best, matched = sounds, target
            if best >= MIN_SCORE:
                scored.append((best, matched, entry))
        scored.sort(key=lambda item: -item[0])  # stable: ties keep catalog order
        return [
            Candidate(
                id=entry.id,
                label=entry.label,
                score=round(value, 1),
                source="catalog",
                in_catalog=True,
                matched=matched,
            )
            for value, matched, entry in scored[:limit]
        ]

    def _names(self, registration_year: int | None) -> dict[str, list[str]]:
        """normalized commercial name -> raw names (private vehicles), cached per year."""
        if registration_year not in self._tax_names:
            index: dict[str, list[str]] = {}
            names = commercial_names(
                self._tax_year, registration_year=registration_year, db_path=self._vehicles_db
            )
            for name in names:
                index.setdefault(normalize(name), []).append(name)
            self._tax_names[registration_year] = index
        return self._tax_names[registration_year]

    def _search_tax_authority(
        self, query: str, normalized: str, registration_year: int | None
    ) -> SearchResult:
        index = self._names(registration_year)
        scored = sorted(
            ((score(normalized, name), name) for name in index), key=lambda item: -item[0]
        )
        scored = [item for item in scored if item[0] >= MIN_SCORE][:MAX_CANDIDATES]
        name_score = {raw: value for value, name in scored for raw in index[name]}
        records = find_by_names(
            list(name_score),
            self._tax_year,
            registration_year=registration_year,
            db_path=self._vehicles_db,
        )
        records.sort(key=lambda r: -name_score[r.commercial_name])  # stable within a name
        candidates = tuple(
            Candidate(
                id=tax_authority_key(record),
                label=(
                    f"{record.commercial_name} {record.registration_year} "
                    f"({record.manufacturer_name}, {record.model_description})"
                ),
                score=round(name_score[record.commercial_name], 1),
                source="tax_authority",
                in_catalog=False,
                matched=normalize(record.commercial_name),
            )
            for record in records[:MAX_CANDIDATES]
        )
        # Several records usually share a name (a name is not a key), so their scores tie and
        # the lead rule keeps this unconfident unless exactly one record matches.
        return SearchResult(
            query=query,
            candidates=candidates,
            confident=_confident([c.score for c in candidates]),
            truncated=len(records) > MAX_CANDIDATES,
        )
