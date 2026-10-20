import pytest

from compass.data.catalog import load_catalog
from compass.engine.context import EngineContext, build_context
from compass.search import Searcher, load_aliases, load_manufacturer_aliases, normalize
from compass.search.search import CONFIDENT_LEAD, CONFIDENT_SCORE, latin_skeleton


@pytest.fixture(scope="module")
def ctx() -> EngineContext:
    return build_context()


@pytest.fixture(scope="module")
def searcher(ctx: EngineContext) -> Searcher:
    return Searcher(
        ctx.catalog,
        ctx.occupations,
        load_aliases(),
        ctx.rules.value_of_use.tax_year,
        manufacturer_aliases=load_manufacturer_aliases(),
    )


# --- normalize --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("  Corolla   CROSS ", "corolla cross"),
        ("מפתח/ת תוכנה", "מפתח תוכנה"),
        ("אנליסט/ית נתונים", "אנליסט נתונימ"),  # final ם -> מ too
        ("נציג/ת מכירות שטח", "נציג מכירות שטח"),
        ("מנהל/ה", "מנהל"),
        ("ספורטז'", "ספורטז"),
        ("ספורטז׳", "ספורטז"),  # Hebrew geresh
        ("סה״כ", "סהכ"),  # gershayim
        ("אם ג'י 4", "אמ גי 4"),
        ("atto3", "atto 3"),
        ("Atto 3", "atto 3"),
        ("mg4", "mg 4"),
        ("אטו3", "אטו 3"),
        ("קרניבל, 2025!", "קרניבל 2025"),
        ("מְנַהֵל", "מנהל"),  # niqqud stripped
        ("ךםןףץ", "כמנפצ"),  # final letters
    ],
)
def test_normalize(text: str, expected: str) -> None:
    assert normalize(text) == expected


# --- aliases ----------------------------------------------------------------------------------


def _is_hebrew(text: str) -> bool:
    return any("א" <= ch <= "ת" for ch in text)


def test_every_catalog_car_has_a_hebrew_alias() -> None:
    aliases = load_aliases()
    for car in load_catalog():
        assert any(_is_hebrew(a) for a in aliases.get(car.commercial_name, ())), car.id


def test_every_alias_points_to_a_catalog_car() -> None:
    names = {car.commercial_name for car in load_catalog()}
    assert set(load_aliases()) <= names


def test_no_alias_names_two_cars() -> None:
    owner: dict[str, str] = {}
    for name, aliases in load_aliases().items():
        for alias in (name, *aliases):
            key = normalize(alias)
            assert owner.setdefault(key, name) == name, f"{alias!r}: {owner[key]} and {name}"


def test_unknown_alias_target_is_rejected(ctx: EngineContext) -> None:
    with pytest.raises(ValueError, match="unknown catalog commercial_name"):
        Searcher(ctx.catalog, ctx.occupations, {"GOLF": ("גולף",)}, 2026)


def test_every_manufacturer_spelling_names_a_catalog_manufacturer(ctx: EngineContext) -> None:
    makers = load_manufacturer_aliases()
    assert {"קיה", "יונדאי", "טויוטה", "מזדה", "סקודה", "טסלה"} <= set(makers)
    with pytest.raises(ValueError, match="unknown catalog manufacturer"):
        Searcher(
            ctx.catalog, ctx.occupations, {}, 2026, manufacturer_aliases={"פולקסווגן": ("vw",)}
        )


# --- the UX walkthrough table -----------------------------------------------------------------


@pytest.mark.parametrize("query", ["מפתח תוכנה", "מפתחת תוכנה"])
def test_developer_is_confident(searcher: Searcher, query: str) -> None:
    result = searcher.search_occupations(query)
    assert result.confident
    assert result.best is not None and result.best.id == "מפתח/ת תוכנה"


def test_unknown_occupation_has_no_candidate(searcher: Searcher) -> None:
    result = searcher.search_occupations("גננות")
    assert result.candidates == () and not result.confident and result.best is None


@pytest.mark.parametrize(
    ("query", "car_id"),
    [
        ("קורולה קורס", "CAR-09"),  # typo
        ("Atto3", "CAR-10"),
        ("אטו 3", "CAR-10"),
        ("atto 3", "CAR-10"),
        ("טסלה", "CAR-14"),
        ("קורולה קרוס", "CAR-09"),
        ("אם ג'י 4", "CAR-06"),
        ("ראב4", "CAR-18"),
        ("סנטה פה", "CAR-20"),
    ],
)
def test_confident_vehicle(searcher: Searcher, query: str, car_id: str) -> None:
    result = searcher.search_vehicles(query)
    assert result.confident, result
    assert result.best is not None and result.best.id == car_id
    assert result.best.source == "catalog" and result.best.in_catalog


def test_typo_beats_the_substring_match(searcher: Searcher) -> None:
    # Documented in compass/search/search.py: WRatio alone gives 90.9 vs 90.0 here.
    first, second = searcher.search_vehicles("קורולה קורס").candidates[:2]
    assert (first.id, second.id) == ("CAR-09", "CAR-07")
    assert first.score >= CONFIDENT_SCORE and first.score - second.score >= CONFIDENT_LEAD


@pytest.mark.parametrize("query", ["קורולה", "corolla", "טויוטה קורולה"])
def test_corolla_alone_is_not_confident(searcher: Searcher, query: str) -> None:
    # The exact alias wins the score lead, but COROLLA CROSS's name strictly extends it, so we
    # ask rather than guess (documented in compass/search/search.py).
    result = searcher.search_vehicles(query)
    assert not result.confident and result.best is None
    assert [c.id for c in result.candidates[:2]] == ["CAR-07", "CAR-09"]


def test_catalog_respects_registration_year(searcher: Searcher) -> None:
    assert searcher.search_vehicles("octavia", registration_year=2025).best is not None
    other_year = searcher.search_vehicles("corolla cross", registration_year=2023)
    assert all(c.source == "tax_authority" for c in other_year.candidates)


# --- tax-authority fallback -------------------------------------------------------------------


def test_tax_authority_returns_full_keys_and_never_picks(searcher: Searcher) -> None:
    result = searcher.search_vehicles("yaris cross hsd", registration_year=2024)
    assert result.candidates and not result.confident
    assert all(c.source == "tax_authority" and not c.in_catalog for c in result.candidates)
    ids = [c.id for c in result.candidates]
    assert len(ids) == len(set(ids)) <= 5
    assert all(len(i.split("-")) == 5 and i.startswith("2026-2024-1-") for i in ids)


def test_tax_authority_only_when_catalog_has_no_match(searcher: Searcher) -> None:
    assert searcher.search_vehicles("golf").candidates[0].source == "tax_authority"
    assert searcher.search_vehicles("קורולה").candidates[0].source == "catalog"


def test_nothing_matches(searcher: Searcher) -> None:
    result = searcher.search_vehicles("zzzzqqqq")
    assert result.candidates == () and not result.confident


# --- search_catalog (a list to pick from) -----------------------------------------------------


@pytest.mark.parametrize(
    ("query", "car_ids"),
    [
        ("קיה", ["CAR-01", "CAR-05", "CAR-11", "CAR-16", "CAR-19"]),  # the manufacturer
        ("יונדאי", ["CAR-08", "CAR-12", "CAR-20"]),
        ("קורולה", ["CAR-07", "CAR-09"]),  # the exact name first, then the longer one
        ("קרוס", ["CAR-02", "CAR-09"]),  # part of a name
        ("אקטביה", ["CAR-15"]),  # a Hebrew spelling no alias has
        ("פיקאנטו", ["CAR-01"]),
        # The manufacturer in English or another spelling (aliases.yaml, `manufacturers`)
        ("kia", ["CAR-05", "CAR-11", "CAR-19", "CAR-01", "CAR-16"]),
        ("KIA", ["CAR-05", "CAR-11", "CAR-19", "CAR-01", "CAR-16"]),
        ("hyundai", ["CAR-12", "CAR-08", "CAR-20"]),
        ("toyota", ["CAR-07", "CAR-09", "CAR-02", "CAR-18"]),
        ("skoda", ["CAR-15"]),
        ("byd", ["CAR-03", "CAR-17", "CAR-10"]),
        ("mg", ["CAR-06"]),
        ("שקודה", ["CAR-15"]),  # a Hebrew spelling the catalog doesn't use
    ],
)
def test_search_catalog_lists_every_car_the_words_may_mean(
    searcher: Searcher, query: str, car_ids: list[str]
) -> None:
    assert [c.id for c in searcher.search_catalog(query)] == car_ids


def test_kia_lists_picanto_and_sportage(searcher: Searcher) -> None:
    ids = {c.id for c in searcher.search_catalog("kia")}
    assert {"CAR-01", "CAR-16"} <= ids  # PICANTO, SPORTAGE HEV: no car alias says "kia"


def test_a_manufacturer_spelling_never_picks_a_car(searcher: Searcher) -> None:
    assert searcher.search_vehicles("kia").best is None


def test_search_catalog_ignores_the_registration_year(searcher: Searcher) -> None:
    assert [c.label for c in searcher.search_catalog("מאזדה 3 2024")] == ["MAZDA 3 2025"]


@pytest.mark.parametrize("query", ["מציון", "golf", "zzzz", "  "])
def test_search_catalog_lists_nothing_for_a_car_not_in_the_catalog(
    searcher: Searcher, query: str
) -> None:
    assert searcher.search_catalog(query) == []


@pytest.mark.parametrize(
    ("hebrew", "latin"),
    [("קודיאק", "kodiaq"), ("אוקטביה", "octavia"), ("פיקנטו", "picanto"), ("קרניבל", "carnival")],
)
def test_a_transliteration_and_the_latin_name_share_a_skeleton(hebrew: str, latin: str) -> None:
    assert latin_skeleton(normalize(hebrew)) == latin_skeleton(normalize(latin))
