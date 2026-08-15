"""The drag polar.

Drag is split the classic way: a part that does not care about lift, and a
part that is the price of making it.

    CD = CD0 + k CL^2

``CD0`` is built up from the parts. Each contributes an equivalent flat plate
area -- the frontal area of a flat plate that would drag as much as it does --
and the sum is divided by the wing reference area. Building it up per part
rather than quoting one number for the aircraft is what makes swapping a wing
change the drag, not just the lift.

Note that ``CD0`` is normalised by the wing area, so fitting a *smaller* wing
raises it even though the aircraft is no draggier in absolute terms.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from aerosizer.config import Configuration

# Raymer's straight-wing estimate returns values above unity for very low
# aspect ratios, which is not physical. Clamp it to something a real wing
# achieves.
MAXIMUM_OSWALD_EFFICIENCY = 0.95


@dataclass(frozen=True)
class DragPolar:
    """How much drag this aircraft makes, at any lift coefficient."""

    zero_lift_drag_coefficient: float
    induced_drag_factor: float
    reference_area: float

    def drag_coefficient(self, lift_coefficient: float) -> float:
        return (
            self.zero_lift_drag_coefficient
            + self.induced_drag_factor * lift_coefficient**2
        )

    @property
    def lift_to_drag_max(self) -> float:
        """Best achievable lift-to-drag ratio, at the minimum-drag speed."""
        return 1.0 / (
            2.0 * math.sqrt(self.induced_drag_factor * self.zero_lift_drag_coefficient)
        )

    @property
    def lift_coefficient_for_minimum_drag(self) -> float:
        return math.sqrt(self.zero_lift_drag_coefficient / self.induced_drag_factor)


def oswald_efficiency(aspect_ratio: float) -> float:
    """Raymer's estimate for a straight, moderately tapered wing."""
    estimate = 1.78 * (1.0 - 0.045 * aspect_ratio**0.68) - 0.64
    return min(estimate, MAXIMUM_OSWALD_EFFICIENCY)


def induced_drag_factor(aspect_ratio: float) -> float:
    """The ``k`` in CD = CD0 + k CL^2."""
    return 1.0 / (math.pi * aspect_ratio * oswald_efficiency(aspect_ratio))


def drag_polar(configuration: Configuration) -> DragPolar:
    """Build the polar for one assembled aircraft."""
    wing = configuration.wing
    flat_plate_area = (
        wing.equivalent_flat_plate_area
        + configuration.empennage.equivalent_flat_plate_area
        + configuration.fuselage.equivalent_flat_plate_area
    )

    return DragPolar(
        zero_lift_drag_coefficient=flat_plate_area / wing.reference_area,
        induced_drag_factor=induced_drag_factor(wing.aspect_ratio),
        reference_area=wing.reference_area,
    )
