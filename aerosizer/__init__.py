"""Modular RC aircraft configuration advisor.

The physics lives here, in a plain importable package with zero UI imports.

Entry points:

    analyze(configuration)          forward model -- evaluate one aircraft
    recommend(requirements, catalog)  the product -- what should I build?

``envelope(mode, catalog)``, which reports what is achievable at all, arrives
at T4.

Everything inside this package is SI: metres, kilograms, seconds, newtons,
radians. Conversion happens only in ``assembly_card``, at the display edge.
"""

from aerosizer.analyze import analyze
from aerosizer.assembly_card import render_assembly_card
from aerosizer.catalog import CatalogError, load_catalog
from aerosizer.config import (
    Candidate,
    Configuration,
    Fidelity,
    FlightMode,
    Recommendation,
    Requirements,
    Results,
)
from aerosizer.parts import Catalog, Empennage, Engine, Fuselage, TailBoom, Wing
from aerosizer.recommend import recommend

__all__ = [
    "Candidate",
    "Catalog",
    "CatalogError",
    "Configuration",
    "Empennage",
    "Engine",
    "Fidelity",
    "FlightMode",
    "Fuselage",
    "Recommendation",
    "Requirements",
    "Results",
    "TailBoom",
    "Wing",
    "analyze",
    "load_catalog",
    "recommend",
    "render_assembly_card",
]
