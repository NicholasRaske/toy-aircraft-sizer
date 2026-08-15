"""Modular RC aircraft configuration advisor.

The physics lives here, in a plain importable package with zero UI imports.

Entry points:

    analyze(configuration, atmosphere)   forward model -- evaluate one aircraft
    recommend(requirements, catalog)     the product -- what should I build?

``achievable(mode, catalog)``, which reports which missions are possible at
all, arrives once the flyability gate exists.

Everything inside this package is SI: metres, kilograms, seconds, newtons,
radians. Conversion happens only in ``assembly_card``, at the display edge.
"""

from aerosizer.analyze import analyze
from aerosizer.assembly_card import render_assembly_card
from aerosizer.atmosphere import SEA_LEVEL_ISA, Atmosphere, atmosphere_at
from aerosizer.catalog import CatalogError, load_catalog
from aerosizer.config import (
    Balance,
    Candidate,
    Configuration,
    Fidelity,
    Limited,
    MassProperties,
    Recommendation,
    Requirements,
    Results,
    SpeedEnvelope,
)
from aerosizer.mass import mass_properties
from aerosizer.mission import (
    CruiseSegment,
    FlightMode,
    InputField,
    LoiterMission,
    LoiterSegment,
    Mission,
    OneWayRangeMission,
    Quantity,
    ReturnRangeMission,
    default_values,
    input_fields,
    mission_fields,
    mission_from,
)
from aerosizer.parts import Catalog, Empennage, Engine, Fuselage, TailBoom, Wing
from aerosizer.recommend import recommend

__all__ = [
    "SEA_LEVEL_ISA",
    "Atmosphere",
    "Balance",
    "Candidate",
    "Catalog",
    "CatalogError",
    "Configuration",
    "CruiseSegment",
    "Empennage",
    "Engine",
    "Fidelity",
    "FlightMode",
    "Fuselage",
    "InputField",
    "Limited",
    "LoiterMission",
    "LoiterSegment",
    "MassProperties",
    "Mission",
    "OneWayRangeMission",
    "Quantity",
    "Recommendation",
    "Requirements",
    "Results",
    "ReturnRangeMission",
    "SpeedEnvelope",
    "TailBoom",
    "Wing",
    "analyze",
    "atmosphere_at",
    "default_values",
    "input_fields",
    "load_catalog",
    "mass_properties",
    "mission_fields",
    "mission_from",
    "recommend",
    "render_assembly_card",
]
