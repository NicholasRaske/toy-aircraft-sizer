"""International Standard Atmosphere.

Density altitude materially changes both stall speed and available engine
power, which is why field elevation and temperature are pilot inputs rather
than buried assumptions. A hot day at a high field is a different aircraft.

Only the troposphere is modelled. This aircraft will not leave it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

STANDARD_GRAVITY = 9.80665
SEA_LEVEL_PRESSURE = 101325.0
SEA_LEVEL_TEMPERATURE = 288.15
SEA_LEVEL_ELEVATION = 0.0

TEMPERATURE_LAPSE_RATE = 0.0065
SPECIFIC_GAS_CONSTANT = 287.0528

# Exponent of the ISA pressure relation, g / (L R).
_PRESSURE_EXPONENT = STANDARD_GRAVITY / (TEMPERATURE_LAPSE_RATE * SPECIFIC_GAS_CONSTANT)


@dataclass(frozen=True)
class Atmosphere:
    """The air the aircraft is flying through."""

    density: float
    temperature: float
    pressure: float


def atmosphere_at(
    elevation: float,
    sea_level_temperature: float = SEA_LEVEL_TEMPERATURE,
) -> Atmosphere:
    """Conditions at a field elevation, on a day of the stated temperature.

    Pressure follows the standard lapse, but density is taken at the *actual*
    temperature -- which is what makes a hot day behave like a higher field.
    """
    pressure = SEA_LEVEL_PRESSURE * (
        1.0 - TEMPERATURE_LAPSE_RATE * elevation / SEA_LEVEL_TEMPERATURE
    ) ** _PRESSURE_EXPONENT
    temperature = sea_level_temperature - TEMPERATURE_LAPSE_RATE * elevation

    return Atmosphere(
        density=pressure / (SPECIFIC_GAS_CONSTANT * temperature),
        temperature=temperature,
        pressure=pressure,
    )


def weight(mass: float) -> float:
    """Newtons of weight for a mass in kilograms."""
    return mass * STANDARD_GRAVITY


def dynamic_pressure(atmosphere: Atmosphere, airspeed: float) -> float:
    return 0.5 * atmosphere.density * airspeed**2


def airspeed_for_lift_coefficient(
    lift: float,
    reference_area: float,
    lift_coefficient: float,
    atmosphere: Atmosphere,
) -> float:
    """The speed at which a wing generates ``lift`` at a given lift coefficient."""
    return math.sqrt(
        2.0 * lift / (atmosphere.density * reference_area * lift_coefficient)
    )


SEA_LEVEL_ISA = atmosphere_at(SEA_LEVEL_ELEVATION)
