"""Loading and validating the part catalogue.

Parts are data, not code. Adding a wing means adding a JSON entry, never
editing a module -- so this is the one place that knows about the on-disk
shape of a part, and it is deliberately strict. A malformed catalogue should
fail loudly at load time, in a workshop, rather than produce a plausible and
wrong assembly card in a field.

Catalogue keys carry explicit unit suffixes. They are converted to internal SI
here, at the data boundary, and never again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aerosizer.parts import Catalog, Empennage, Engine, Fuselage, TailBoom, Wing

# Engine data sheets quote brake specific fuel consumption in g/kWh.
# Internally it is kilograms of fuel per joule of shaft work.
KILOGRAMS_PER_JOULE_PER_GRAM_PER_KILOWATT_HOUR = 1.0 / (1000.0 * 3.6e6)


class CatalogError(Exception):
    """Raised when a part file is missing, malformed, or physically absurd."""


def load_catalog(parts_directory: Path) -> Catalog:
    """Read a complete catalogue from a directory of JSON part files."""
    fuselage = _parse_fuselage(_read_part_file(parts_directory / "fuselage.json"))
    engine = _parse_sole_engine(_read_part_file(parts_directory / "engines.json"))
    wings = _parse_wings(_read_part_file(parts_directory / "wings.json"))
    empennages = _parse_empennages(_read_part_file(parts_directory / "empennages.json"))

    return Catalog(
        fuselage=fuselage,
        engine=engine,
        wings=wings,
        empennages=empennages,
    )


def _read_part_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise CatalogError(f"Part file not found: {path}")
    try:
        with path.open(encoding="utf-8") as handle:
            contents = json.load(handle)
    except json.JSONDecodeError as error:
        raise CatalogError(f"Part file {path.name} is not valid JSON: {error}") from error
    if not isinstance(contents, dict):
        raise CatalogError(f"Part file {path.name} must contain a JSON object")
    return contents


def _parse_wings(document: dict[str, Any]) -> tuple[Wing, ...]:
    entries = _entry_list(document, "wings", "wings.json")
    wings = tuple(_parse_wing(entry) for entry in entries)
    _reject_duplicate_names(wings, "wing")
    return wings


def _parse_wing(entry: dict[str, Any]) -> Wing:
    name = _text(entry, "name", "wing")
    source = f"wing '{name}'"
    wing = Wing(
        name=name,
        airfoil=_text(entry, "airfoil", source),
        reference_area=_positive(entry, "reference_area_m2", source),
        span=_positive(entry, "span_m", source),
        root_chord=_positive(entry, "root_chord_m", source),
        tip_chord=_positive(entry, "tip_chord_m", source),
        max_lift_coefficient=_positive(entry, "max_lift_coefficient", source),
        mass=_positive(entry, "mass_kg", source),
        aerodynamic_centre_station=_positive(entry, "aerodynamic_centre_station_m", source),
    )
    if wing.tip_chord > wing.root_chord:
        raise CatalogError(f"{source}: tip chord exceeds root chord")
    return wing


def _parse_empennages(document: dict[str, Any]) -> tuple[Empennage, ...]:
    entries = _entry_list(document, "empennages", "empennages.json")
    empennages = tuple(_parse_empennage(entry) for entry in entries)
    _reject_duplicate_names(empennages, "empennage")
    return empennages


def _parse_empennage(entry: dict[str, Any]) -> Empennage:
    name = _text(entry, "name", "empennage")
    source = f"empennage '{name}'"
    return Empennage(
        name=name,
        horizontal_tail_area=_positive(entry, "horizontal_tail_area_m2", source),
        vertical_tail_area=_positive(entry, "vertical_tail_area_m2", source),
        mass=_positive(entry, "mass_kg", source),
        nominal_aerodynamic_centre_station=_positive(
            entry, "nominal_aerodynamic_centre_station_m", source
        ),
    )


def _parse_fuselage(document: dict[str, Any]) -> Fuselage:
    entry = _entry_object(document, "fuselage", "fuselage.json")
    name = _text(entry, "name", "fuselage")
    source = f"fuselage '{name}'"
    boom_entry = _entry_object(entry, "tail_boom", source)

    tail_boom = TailBoom(
        root_station=_positive(boom_entry, "root_station_m", f"{source} tail boom"),
        max_extension=_positive(boom_entry, "max_extension_m", f"{source} tail boom"),
        detent_spacing=_positive(boom_entry, "detent_spacing_m", f"{source} tail boom"),
        mass_per_metre=_positive(boom_entry, "mass_per_metre_kg_per_m", f"{source} tail boom"),
    )
    if tail_boom.detent_spacing > tail_boom.max_extension:
        raise CatalogError(f"{source}: boom detent spacing exceeds its total travel")

    return Fuselage(
        name=name,
        structure_mass=_positive(entry, "structure_mass_kg", source),
        structure_centre_of_mass_station=_positive(
            entry, "structure_centre_of_mass_station_m", source
        ),
        payload_station=_positive(entry, "payload_station_m", source),
        fuel_tank_station=_positive(entry, "fuel_tank_station_m", source),
        max_fuel_mass=_positive(entry, "max_fuel_mass_kg", source),
        tail_boom=tail_boom,
    )


def _parse_sole_engine(document: dict[str, Any]) -> Engine:
    """Parse the one engine this airframe flies with.

    Exactly one engine is supported today. If the engine ever becomes a fourth
    selectable module, this is the function that changes -- and until then, a
    second entry should fail loudly rather than be silently ignored.
    """
    entries = _entry_list(document, "engines", "engines.json")
    if len(entries) != 1:
        raise CatalogError(
            f"engines.json must define exactly one engine, found {len(entries)}. "
            "Engine choice is not yet a configurable module."
        )

    entry = entries[0]
    name = _text(entry, "name", "engine")
    source = f"engine '{name}'"
    quoted_consumption = _positive(entry, "best_specific_fuel_consumption_g_per_kwh", source)
    propeller_efficiency = _positive(entry, "propeller_efficiency", source)
    if not 0.0 < propeller_efficiency < 1.0:
        raise CatalogError(f"{source}: propeller efficiency must lie between 0 and 1")

    return Engine(
        name=name,
        max_shaft_power=_positive(entry, "max_shaft_power_w", source),
        best_specific_fuel_consumption=(
            quoted_consumption * KILOGRAMS_PER_JOULE_PER_GRAM_PER_KILOWATT_HOUR
        ),
        propeller_efficiency=propeller_efficiency,
        mass=_positive(entry, "mass_kg", source),
        station=_positive(entry, "station_m", source),
    )


def _entry_list(document: dict[str, Any], key: str, filename: str) -> list[dict[str, Any]]:
    if key not in document:
        raise CatalogError(f"{filename} is missing its '{key}' list")
    entries = document[key]
    if not isinstance(entries, list) or not entries:
        raise CatalogError(f"{filename}: '{key}' must be a non-empty list")
    for entry in entries:
        if not isinstance(entry, dict):
            raise CatalogError(f"{filename}: every entry in '{key}' must be an object")
    return entries


def _entry_object(document: dict[str, Any], key: str, source: str) -> dict[str, Any]:
    if key not in document:
        raise CatalogError(f"{source} is missing its '{key}' object")
    entry = document[key]
    if not isinstance(entry, dict):
        raise CatalogError(f"{source}: '{key}' must be an object")
    return entry


def _text(entry: dict[str, Any], key: str, source: str) -> str:
    if key not in entry:
        raise CatalogError(f"{source} is missing '{key}'")
    value = entry[key]
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{source}: '{key}' must be a non-empty string")
    return value


def _positive(entry: dict[str, Any], key: str, source: str) -> float:
    if key not in entry:
        raise CatalogError(f"{source} is missing '{key}'")
    value = entry[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CatalogError(f"{source}: '{key}' must be a number")
    if value <= 0.0:
        raise CatalogError(f"{source}: '{key}' must be greater than zero, got {value}")
    return float(value)


def _reject_duplicate_names(parts: tuple[Any, ...], kind: str) -> None:
    seen: set[str] = set()
    for part in parts:
        if part.name in seen:
            raise CatalogError(f"Duplicate {kind} name in catalogue: '{part.name}'")
        seen.add(part.name)
