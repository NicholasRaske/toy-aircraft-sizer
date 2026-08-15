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
LITRES_PER_CUBIC_METRE = 1000.0


def hours_to_seconds(hours: float) -> float:
    return hours * SECONDS_PER_HOUR


def metres_to_millimetres(metres: float) -> float:
    return metres * MILLIMETRES_PER_METRE


def cubic_metres_to_litres(cubic_metres: float) -> float:
    return cubic_metres * LITRES_PER_CUBIC_METRE


def format_duration(seconds: float) -> str:
    """Render a duration the way a pilot reads it: ``1 h 04 min``."""
    hours, minutes = divmod(round(seconds / SECONDS_PER_MINUTE), 60)
    if hours == 0:
        return f"{minutes} min"
    return f"{hours} h {minutes:02d} min"
