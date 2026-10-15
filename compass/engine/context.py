"""EngineContext: the rules, catalog and occupations one calculation reads, checked together.

Cross-file consistency (e.g. every rules.family_track.cars id is a catalog car in group
"משפחתי") cannot be checked by any one loader, so it is checked here.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from compass.data.catalog import FAMILY_GROUP, CatalogCar, load_catalog
from compass.data.occupations import Occupation, load_occupations
from compass.rules import Rules, load_rules


class ContextError(ValueError):
    """The rules, catalog and occupations contradict each other."""


@dataclass(frozen=True)
class EngineContext:
    rules: Rules
    catalog: Mapping[str, CatalogCar]  # by car id, catalog order
    occupations: Mapping[str, Occupation]  # by exact title

    def is_family_car(self, car_id: str) -> bool:
        return car_id in self.rules.family_track.cars


def build_context(
    rules: Rules | None = None,
    catalog: tuple[CatalogCar, ...] | None = None,
    occupations: tuple[Occupation, ...] | None = None,
) -> EngineContext:
    """Bundle the data (loading the default files for anything not given) and validate it."""
    rules = load_rules() if rules is None else rules
    catalog = load_catalog() if catalog is None else catalog
    occupations = load_occupations() if occupations is None else occupations

    problems: list[str] = []
    by_id = {car.id: car for car in catalog}
    if len(by_id) != len(catalog):
        problems.append("catalog: duplicate car ids")
    for car_id in rules.family_track.cars:
        car = by_id.get(car_id)
        if car is None:
            problems.append(f"family_track.cars: {car_id} is not in the catalog")
        elif car.group != FAMILY_GROUP:
            problems.append(
                f"family_track.cars: {car_id} has catalog group {car.group!r}, "
                f"expected {FAMILY_GROUP!r}"
            )
    for car in catalog:
        if car.group == FAMILY_GROUP and car.id not in rules.family_track.cars:
            problems.append(
                f"catalog: {car.id} is in group {FAMILY_GROUP!r} but not listed in "
                "family_track.cars"
            )
        elif car.group != FAMILY_GROUP and car.group not in rules.group_order:
            problems.append(f"catalog: {car.id} has unknown group {car.group!r}")
    by_title = {occupation.title: occupation for occupation in occupations}
    if len(by_title) != len(occupations):
        problems.append("occupations: duplicate titles")
    if problems:
        raise ContextError("Inconsistent engine data:\n" + "\n".join(f"  - {p}" for p in problems))
    return EngineContext(
        rules=rules, catalog=MappingProxyType(by_id), occupations=MappingProxyType(by_title)
    )
