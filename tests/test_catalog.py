"""The catalogue must load, and must refuse to load anything dubious.

A malformed part file should fail in a workshop, loudly, rather than produce a
plausible and wrong assembly card in a field.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aerosizer import CatalogError, load_catalog


def test_shipped_catalogue_loads(catalog):
    assert catalog.wings, "catalogue must define at least one wing"
    assert catalog.empennages, "catalogue must define at least one empennage"
    assert catalog.fuselage.name
    assert catalog.engine.name


def test_wing_geometry_is_derived_not_declared(catalog):
    surveyor = _wing_named(catalog, "Surveyor")

    # Aspect ratio comes from span and area, so a catalogue can never declare
    # a value that contradicts its own planform.
    assert surveyor.aspect_ratio == pytest.approx(3.8**2 / 1.6)

    # Trapezoidal MAC, hand-checked: taper 0.75, root chord 0.48 m gives
    # (2/3)(0.48)(1 + 0.75 + 0.5625) / 1.75 = 0.4229 m. Slightly greater than
    # the 0.42 m mean geometric chord, as it must be for a tapered wing.
    assert surveyor.mean_aerodynamic_chord == pytest.approx(0.4229, abs=1e-4)
    assert surveyor.mean_aerodynamic_chord > 0.5 * (
        surveyor.root_chord + surveyor.tip_chord
    )


def test_mean_aerodynamic_chord_of_untapered_wing_equals_its_chord():
    from aerosizer import Wing

    untapered = Wing(
        name="Test",
        airfoil="NACA 0012",
        reference_area=2.0,
        span=4.0,
        root_chord=0.5,
        tip_chord=0.5,
        max_lift_coefficient=1.2,
        clean_flat_plate_area=0.012,
        excrescence_flat_plate_area=0.002,
        oswald_efficiency=0.78,
        mass=3.0,
        aerodynamic_centre_station=0.6,
    )
    assert untapered.mean_aerodynamic_chord == pytest.approx(0.5)


def test_engine_fuel_consumption_is_converted_to_si(catalog):
    # 550 g/kWh is the quoted figure; internally it is kg per joule.
    expected = 550.0 / (1000.0 * 3.6e6)
    assert catalog.engine.best_specific_fuel_consumption == pytest.approx(expected)


def test_tail_boom_quantises_to_detents(catalog):
    boom = catalog.fuselage.tail_boom

    # An instruction the pilot cannot execute is an instruction that is wrong.
    assert boom.quantise(0.3472) == pytest.approx(0.35)
    assert boom.quantise(0.3449) == pytest.approx(0.34)


def test_tail_boom_quantisation_stays_within_travel(catalog):
    boom = catalog.fuselage.tail_boom

    assert boom.quantise(-0.1) == pytest.approx(0.0)
    assert boom.quantise(boom.max_extension * 2.0) == pytest.approx(boom.max_extension)


def test_missing_part_file_is_reported(tmp_path):
    with pytest.raises(CatalogError, match="not found"):
        load_catalog(tmp_path)


def test_negative_mass_is_rejected(tmp_path, parts_directory):
    parts = _copy_catalogue(parts_directory, tmp_path)
    _mutate(parts / "wings.json", lambda document: document["wings"][0].update({"mass_kg": -1.0}))

    with pytest.raises(CatalogError, match="greater than zero"):
        load_catalog(parts)


def test_duplicate_wing_names_are_rejected(tmp_path, parts_directory):
    parts = _copy_catalogue(parts_directory, tmp_path)
    _mutate(parts / "wings.json", lambda document: document["wings"].append(document["wings"][0]))

    with pytest.raises(CatalogError, match="Duplicate wing name"):
        load_catalog(parts)


def test_tip_chord_larger_than_root_is_rejected(tmp_path, parts_directory):
    parts = _copy_catalogue(parts_directory, tmp_path)
    _mutate(
        parts / "wings.json",
        lambda document: document["wings"][0].update({"tip_chord_m": 99.0}),
    )

    with pytest.raises(CatalogError, match="tip chord exceeds root chord"):
        load_catalog(parts)


def test_second_engine_is_rejected_rather_than_ignored(tmp_path, parts_directory):
    parts = _copy_catalogue(parts_directory, tmp_path)
    _mutate(
        parts / "engines.json",
        lambda document: document["engines"].append(document["engines"][0]),
    )

    with pytest.raises(CatalogError, match="exactly one engine"):
        load_catalog(parts)


def _wing_named(catalog, name):
    return next(wing for wing in catalog.wings if wing.name == name)


def _copy_catalogue(source_directory: Path, destination: Path) -> Path:
    parts = destination / "parts"
    parts.mkdir()
    for source in source_directory.glob("*.json"):
        (parts / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return parts


def _mutate(path: Path, change) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document), encoding="utf-8")
