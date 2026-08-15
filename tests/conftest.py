"""Shared fixtures.

The shipped catalogue is used directly rather than mocked, because it is data
the tool must always be able to load. A synthetic catalogue generator, for the
property tests that need volume and variety, arrives at T3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aerosizer import Catalog, Configuration, Requirements, load_catalog
from aerosizer.config import FlightMode
from aerosizer.units import hours_to_seconds

PARTS_DIRECTORY = Path(__file__).parent.parent / "parts"


@pytest.fixture
def parts_directory() -> Path:
    return PARTS_DIRECTORY


@pytest.fixture
def catalog() -> Catalog:
    return load_catalog(PARTS_DIRECTORY)


@pytest.fixture
def loiter_requirements() -> Requirements:
    return Requirements(
        mode=FlightMode.LOITER,
        duration=hours_to_seconds(1.0),
        payload_mass=4.0,
    )


@pytest.fixture
def baseline_configuration(catalog: Catalog) -> Configuration:
    """The first wing and empennage in the catalogue, fully determined."""
    return Configuration(
        fuselage=catalog.fuselage,
        engine=catalog.engine,
        wing=catalog.wings[0],
        empennage=catalog.empennages[0],
        tail_extension=0.0,
        fuel_mass=2.0,
        payload_mass=4.0,
    )
