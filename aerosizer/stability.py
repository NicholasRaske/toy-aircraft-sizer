"""Longitudinal stability: where the aircraft balances, and how far that is
from where it would stop being stable.

The neutral point is the station at which pitching moment stops caring about
lift. Ahead of it the aircraft is stable, behind it is not, and the gap between
it and the centre of gravity -- measured in mean chords -- is the static
margin.

Neutral points are not computed here. They come from the catalogue, generated
offline by a vortex lattice model in ``tools/``, sampled against tail extension
and interpolated between. That keeps a genuinely expensive calculation off the
aircraft without reducing it to a rule of thumb.

Extending the boom carries the tail further aft, which moves the neutral point
aft faster than it moves the centre of gravity, because the boom and empennage
are light while the tail's aerodynamic contribution grows with its arm. Static
margin therefore rises monotonically with extension, which is what makes the
solve a simple bisection.
"""

from __future__ import annotations

from collections.abc import Callable

from aerosizer.config import Balance, Configuration, MassProperties

# What this class of aircraft is trimmed to. Below the minimum it is twitchy;
# above the maximum it is stable to the point of being unresponsive, and
# carries more trim drag than it needs to.
TARGET_STATIC_MARGIN = 0.12
MINIMUM_STATIC_MARGIN = 0.05
MAXIMUM_STATIC_MARGIN = 0.20

SOLVE_TOLERANCE = 1e-4


def static_margin(
    neutral_point_station: float,
    centre_of_gravity_station: float,
    mean_aerodynamic_chord: float,
) -> float:
    """How far the balance point sits ahead of the neutral point, in chords."""
    return (neutral_point_station - centre_of_gravity_station) / mean_aerodynamic_chord


def horizontal_tail_volume(configuration: Configuration, centre_of_gravity: float) -> float:
    wing = configuration.wing
    arm = (
        configuration.empennage.aerodynamic_centre_station(configuration.tail_extension)
        - centre_of_gravity
    )
    return (configuration.empennage.horizontal_tail_area * arm) / (
        wing.reference_area * wing.mean_aerodynamic_chord
    )


def vertical_tail_volume(configuration: Configuration, centre_of_gravity: float) -> float:
    wing = configuration.wing
    arm = (
        configuration.empennage.aerodynamic_centre_station(configuration.tail_extension)
        - centre_of_gravity
    )
    return (configuration.empennage.vertical_tail_area * arm) / (
        wing.reference_area * wing.span
    )


def balance_of(configuration: Configuration, mass: MassProperties) -> Balance:
    """Stability of one configuration at one loading."""
    neutral_point = configuration.neutral_point_curve.station_at(configuration.tail_extension)
    centre_of_gravity = mass.centre_of_gravity_station

    return Balance(
        neutral_point_station=neutral_point,
        static_margin=static_margin(
            neutral_point, centre_of_gravity, configuration.wing.mean_aerodynamic_chord
        ),
        horizontal_tail_volume=horizontal_tail_volume(configuration, centre_of_gravity),
        vertical_tail_volume=vertical_tail_volume(configuration, centre_of_gravity),
    )


def solve_tail_extension(
    margin_at: Callable[[float], float],
    maximum_extension: float,
    target: float = TARGET_STATIC_MARGIN,
) -> float:
    """Boom extension that trims the aircraft to a target static margin.

    Bisection is safe here because static margin rises monotonically with
    extension. Where the target lies outside what the boom can reach, the
    answer is clamped to the travel available -- the aircraft is then as close
    as it can be, and how close is worth reporting rather than hiding.
    """
    if margin_at(0.0) >= target:
        return 0.0
    if margin_at(maximum_extension) <= target:
        return maximum_extension

    lower, upper = 0.0, maximum_extension
    while upper - lower > SOLVE_TOLERANCE:
        middle = 0.5 * (lower + upper)
        if margin_at(middle) < target:
            lower = middle
        else:
            upper = middle
    return 0.5 * (lower + upper)
