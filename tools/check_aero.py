"""Check our drag polar against AeroSandbox.

Our model has three invented numbers per configuration: a flat-plate drag area
per part, an Oswald efficiency from a textbook correlation, and a maximum lift
coefficient. This runs the same geometry through AeroSandbox's component
buildup and reports how far apart the two are.

AeroSandbox sweeps angle of attack; the resulting drag polar is fitted to the
same parabolic form we use, so the comparison is like for like:

    CD = CD0 + k CL^2

Run it with::

    python -m tools.check_aero
"""

from __future__ import annotations

import itertools
from pathlib import Path

import aerosandbox as asb
import numpy as np

from aerosizer import Configuration, load_catalog
from aerosizer.aero import drag_polar, oswald_efficiency
from tools.asb_geometry import airplane_for

PARTS_DIRECTORY = Path(__file__).parent.parent / "parts"

SWEEP_ALPHAS = np.linspace(-2.0, 8.0, 11)
SWEEP_AIRSPEED = 16.0


def parabolic_fit(lift: np.ndarray, drag: np.ndarray) -> tuple[float, float]:
    """Least-squares fit of CD = CD0 + k CL^2 to a computed polar."""
    basis = np.vstack([np.ones_like(lift), lift**2]).T
    zero_lift_drag, induced_factor = np.linalg.lstsq(basis, drag, rcond=None)[0]
    return float(zero_lift_drag), float(induced_factor)


def aerosandbox_polar(configuration: Configuration) -> tuple[float, float]:
    airplane = airplane_for(configuration)
    operating_point = asb.OperatingPoint(
        atmosphere=asb.Atmosphere(altitude=0.0),
        velocity=SWEEP_AIRSPEED,
        alpha=SWEEP_ALPHAS,
    )
    aero = asb.AeroBuildup(airplane=airplane, op_point=operating_point).run()

    return parabolic_fit(np.asarray(aero["CL"]), np.asarray(aero["CD"]))


def compare(configuration: Configuration) -> dict[str, tuple[float, float]]:
    ours = drag_polar(configuration)
    their_cd0, their_k = aerosandbox_polar(configuration)

    aspect_ratio = configuration.wing.aspect_ratio
    their_efficiency = 1.0 / (np.pi * aspect_ratio * their_k)

    return {
        "CD0": (ours.zero_lift_drag_coefficient, their_cd0),
        "k": (ours.induced_drag_factor, their_k),
        "Oswald e": (oswald_efficiency(aspect_ratio), their_efficiency),
        "L/D max": (ours.lift_to_drag_max, 1.0 / (2.0 * (their_k * their_cd0) ** 0.5)),
    }


def main() -> int:
    catalog = load_catalog(PARTS_DIRECTORY)

    for wing, empennage in itertools.product(catalog.wings, catalog.empennages):
        configuration = Configuration(
            fuselage=catalog.fuselage,
            engine=catalog.engine,
            wing=wing,
            empennage=empennage,
            tail_extension=0.0,
            fuel_mass=0.3,
            payload_mass=4.0,
        )

        print(f"\n{wing.name} + {empennage.name}")
        print(f"  {'':10}{'ours':>10}{'AeroSandbox':>14}{'delta':>10}")
        for quantity, (ours, theirs) in compare(configuration).items():
            delta = (theirs - ours) / ours * 100.0
            print(f"  {quantity:10}{ours:10.4f}{theirs:14.4f}{delta:9.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
