"""Unit conversion helpers for the display edge.

Everything inside ``aerosizer`` is SI: metres, kilograms, seconds, newtons,
radians. Nothing in the physics ever converts. These helpers exist so that
conversion happens exactly once, at the point where a number is shown to a
pilot, and so that the conversion factors have a single home.

Data files under ``parts/`` carry explicit unit suffixes on their keys
(``mass_kg``, ``span_m``) because a JSON file has no other way to declare its
units. Those suffixes are stripped when the catalogue is parsed.
"""

from __future__ import annotations

SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0
GRAMS_PER_KILOGRAM = 1000.0
METRES_PER_KILOMETRE = 1000.0
MILLIMETRES_PER_METRE = 1000.0
LITRES_PER_CUBIC_METRE = 1000.0


def hours_to_seconds(hours: float) -> float:
    return hours * SECONDS_PER_HOUR


def minutes_to_seconds(minutes: float) -> float:
    return minutes * SECONDS_PER_MINUTE


def kilometres_to_metres(kilometres: float) -> float:
    return kilometres * METRES_PER_KILOMETRE


def metres_to_millimetres(metres: float) -> float:
    return metres * MILLIMETRES_PER_METRE


def cubic_metres_to_litres(cubic_metres: float) -> float:
    return cubic_metres * LITRES_PER_CUBIC_METRE


def format_distance(metres: float) -> str:
    return f"{metres / METRES_PER_KILOMETRE:.1f} km"


def format_mass(kilograms: float) -> str:
    return f"{kilograms:.1f} kg"


def format_fuel_mass(kilograms: float) -> str:
    """Fuel loads on this aircraft are small enough that grams read better."""
    if kilograms < 1.0:
        return f"{kilograms * GRAMS_PER_KILOGRAM:.0f} g"
    return f"{kilograms:.2f} kg"


def format_speed(metres_per_second: float) -> str:
    return f"{metres_per_second:.1f} m/s"


def format_duration(seconds: float) -> str:
    """Render a duration the way a pilot reads it: ``1 h 04 min``."""
    hours, minutes = divmod(round(seconds / SECONDS_PER_MINUTE), 60)
    if hours == 0:
        return f"{minutes} min"
    return f"{hours} h {minutes:02d} min"
