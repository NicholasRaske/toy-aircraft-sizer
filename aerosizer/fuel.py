"""Fuel: the variable that makes this an aircraft-sizing problem.

Fuel burns off in flight, so the aircraft gets lighter and its centre of
gravity moves. Both matter, and both are handled elsewhere. This module owns
only the fuel itself: what it weighs, and what volume the pilot has to pour in
to get that weight.

The pilot fills a tank, not a mass budget, so a fuel instruction is always
issued as a volume.
"""

from __future__ import annotations

# Automotive petrol at typical field temperatures. Density varies by a few
# percent with temperature and blend; that is well inside the accuracy of
# everything else in the fuel path.
PETROL_DENSITY = 720.0


def volume_for_mass(fuel_mass: float) -> float:
    """Cubic metres of petrol weighing ``fuel_mass`` kilograms."""
    return fuel_mass / PETROL_DENSITY


def mass_for_volume(fuel_volume: float) -> float:
    """Kilograms of petrol occupying ``fuel_volume`` cubic metres."""
    return fuel_volume * PETROL_DENSITY
