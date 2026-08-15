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
MILLIMETRES_PER_METRE = 1000.0
GRAMS_PER_KILOGRAM = 1000.0
LITRES_PER_CUBIC_METRE = 1000.0


def hours_to_seconds(hours: float) -> float:
    return hours * SECONDS_PER_HOUR


def seconds_to_hours(seconds: float) -> float:
    return seconds / SECONDS_PER_HOUR


def metres_to_millimetres(metres: float) -> float:
    return metres * MILLIMETRES_PER_METRE


def kilograms_to_grams(kilograms: float) -> float:
    return kilograms * GRAMS_PER_KILOGRAM


def cubic_metres_to_litres(cubic_metres: float) -> float:
    return cubic_metres * LITRES_PER_CUBIC_METRE


def format_duration(seconds: float) -> str:
    """Render a duration the way a pilot reads it: ``1 h 04 min``."""
    whole_minutes = int(round(seconds / SECONDS_PER_MINUTE))
    hours, minutes = divmod(whole_minutes, 60)
    if hours == 0:
        return f"{minutes} min"
    return f"{hours} h {minutes:02d} min"
