"""Translating a configuration into AeroSandbox geometry.

This is the bridge, and it only crosses one way: it reads ``aerosizer`` domain
objects and produces an ``asb.Airplane``. Nothing in ``aerosizer`` knows this
module exists.

The catalogue records what a part weighs and where it sits, not what it looks
like. Turning those into a three-dimensional shape needs assumptions, and they
are all gathered in SHAPE ASSUMPTIONS below rather than scattered through the
construction. When the catalogue grows real geometry, this is the section that
shrinks.
"""

from __future__ import annotations

import aerosandbox as asb

from aerosizer.config import Configuration
from aerosizer.parts import Empennage, Wing

# ------------------------------------------------------------ SHAPE ASSUMPTIONS
#
# None of these are in the catalogue yet. Each is a guess that only affects
# drawing and drag buildup, never mass or balance.

TAIL_AIRFOIL = "naca0010"
HORIZONTAL_TAIL_ASPECT_RATIO = 4.0
VERTICAL_TAIL_ASPECT_RATIO = 1.5

# Body radius at fractions along the main body. A blunt nose, a parallel middle
# wide enough for payload and tank, and a taper into the tail boom.
BODY_PROFILE = (
    (0.00, 0.010),
    (0.08, 0.055),
    (0.20, 0.075),
    (0.45, 0.078),
    (0.65, 0.060),
    (0.85, 0.038),
    (1.00, 0.030),
)

# The boom is a slender tube carrying the empennage aft of the main body.
BOOM_RADIUS = 0.022
BOOM_OVERHANG = 0.08

# Where the wing sits vertically, and how far the fin rises above the boom.
WING_VERTICAL_OFFSET = 0.06
FIN_ROOT_OFFSET = 0.015

QUARTER_CHORD = 0.25


def airplane_for(configuration: Configuration) -> asb.Airplane:
    """Build the AeroSandbox model of one assembled aircraft."""
    return asb.Airplane(
        name=f"{configuration.wing.name} + {configuration.empennage.name}",
        xyz_ref=[configuration.wing.aerodynamic_centre_station, 0.0, 0.0],
        wings=[
            main_wing_of(configuration.wing),
            horizontal_tail_of(configuration.empennage, configuration.tail_extension),
            vertical_tail_of(configuration.empennage, configuration.tail_extension),
        ],
        fuselages=[body_of(configuration)],
    )


def main_wing_of(wing: Wing) -> asb.Wing:
    """A straight tapered wing, quarter chord on its aerodynamic centre."""
    airfoil = asb.Airfoil(_airfoil_name(wing.airfoil))
    half_span = wing.span / 2.0

    root_leading_edge = wing.aerodynamic_centre_station - QUARTER_CHORD * wing.root_chord
    tip_leading_edge = wing.aerodynamic_centre_station - QUARTER_CHORD * wing.tip_chord

    return asb.Wing(
        name=wing.name,
        symmetric=True,
        xsecs=[
            asb.WingXSec(
                xyz_le=[root_leading_edge, 0.0, WING_VERTICAL_OFFSET],
                chord=wing.root_chord,
                airfoil=airfoil,
            ),
            asb.WingXSec(
                xyz_le=[tip_leading_edge, half_span, WING_VERTICAL_OFFSET],
                chord=wing.tip_chord,
                airfoil=airfoil,
            ),
        ],
    )


def horizontal_tail_of(empennage: Empennage, tail_extension: float) -> asb.Wing:
    station = empennage.aerodynamic_centre_station(tail_extension)
    span, chord = _planform(empennage.horizontal_tail_area, HORIZONTAL_TAIL_ASPECT_RATIO)
    leading_edge = station - QUARTER_CHORD * chord

    return asb.Wing(
        name="Horizontal tail",
        symmetric=True,
        xsecs=[
            asb.WingXSec(
                xyz_le=[leading_edge, offset, 0.0],
                chord=chord,
                airfoil=asb.Airfoil(TAIL_AIRFOIL),
            )
            for offset in (0.0, span / 2.0)
        ],
    )


def vertical_tail_of(empennage: Empennage, tail_extension: float) -> asb.Wing:
    station = empennage.aerodynamic_centre_station(tail_extension)

    # A fin's aspect ratio is measured on its height, since it has no mirror
    # half. Treating it like a wing would give a fin wider than it is tall.
    height = (empennage.vertical_tail_area * VERTICAL_TAIL_ASPECT_RATIO) ** 0.5
    chord = empennage.vertical_tail_area / height
    leading_edge = station - QUARTER_CHORD * chord

    return asb.Wing(
        name="Vertical tail",
        symmetric=False,
        xsecs=[
            asb.WingXSec(
                xyz_le=[leading_edge, 0.0, FIN_ROOT_OFFSET + rise],
                chord=chord,
                airfoil=asb.Airfoil(TAIL_AIRFOIL),
            )
            for rise in (0.0, height)
        ],
    )


def body_of(configuration: Configuration) -> asb.Fuselage:
    """The main body, plus the boom that carries the empennage aft of it."""
    boom = configuration.fuselage.tail_boom
    body_length = boom.root_station

    _, tail_chord = _planform(
        configuration.empennage.horizontal_tail_area, HORIZONTAL_TAIL_ASPECT_RATIO
    )
    boom_end = (
        configuration.empennage.aerodynamic_centre_station(configuration.tail_extension)
        + (1.0 - QUARTER_CHORD) * tail_chord
        + BOOM_OVERHANG
    )

    sections = [
        asb.FuselageXSec(xyz_c=[fraction * body_length, 0.0, 0.0], radius=radius)
        for fraction, radius in BODY_PROFILE
    ]
    sections.extend(
        asb.FuselageXSec(xyz_c=[station, 0.0, 0.0], radius=BOOM_RADIUS)
        for station in (body_length + 0.02, boom_end)
    )

    return asb.Fuselage(name=configuration.fuselage.name, xsecs=sections)


def _planform(area: float, aspect_ratio: float) -> tuple[float, float]:
    """Span and constant chord of an untapered surface of a given area."""
    span = (area * aspect_ratio) ** 0.5
    return span, area / span


def _airfoil_name(catalogue_name: str) -> str:
    """``NACA 4412`` in the catalogue, ``naca4412`` to AeroSandbox."""
    return catalogue_name.replace(" ", "").lower()
