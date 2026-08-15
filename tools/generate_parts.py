"""Generate the aerodynamic half of the part catalogue with AeroSandbox.

Build-time only. This writes numbers into ``parts/*.json``; the aircraft reads
that JSON and never runs AeroSandbox.

Ownership is split, because the two halves are known in different ways:

    hand-authored   mass, stations, span, chords, areas, and the excrescence
                    allowance -- things measured off hardware, or judged
    generated       clean profile drag, Oswald efficiency, maximum lift, and
                    the neutral point -- things computed from the shape

Clean drag is attributed per part by modelling each part on its own. That
misses interference between them, which is why the full assembly is also run
and the parts scaled so they add up to it.

Run it with::

    python -m tools.generate_parts
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import aerosandbox as asb
import numpy as np

from aerosizer import Configuration, load_catalog
from aerosizer.parts import Catalog, Wing
from tools.asb_geometry import (
    airplane_for,
    body_of,
    horizontal_tail_of,
    main_wing_of,
    vertical_tail_of,
)

PARTS_DIRECTORY = Path(__file__).parent.parent / "parts"

REFERENCE_AIRSPEED = 16.0
POLAR_ALPHAS = np.linspace(-2.0, 8.0, 11)
STALL_ALPHAS = np.linspace(0.0, 20.0, 41)

# A finite wing reaches less than its aerofoil's two-dimensional maximum: the
# tip unloads, and the section stalls unevenly along the span. Standard
# first-order allowance, and quite good enough for a tool that recommends
# rather than certifies.
THREE_DIMENSIONAL_LIFT_FACTOR = 0.9

# Tail extensions at which the neutral point is recorded. The solve
# interpolates between them.
EXTENSION_SAMPLES = (0.0, 0.1, 0.2, 0.3, 0.4)

AIR = asb.Atmosphere(altitude=0.0)


def _operating_point(alpha) -> asb.OperatingPoint:
    return asb.OperatingPoint(atmosphere=AIR, velocity=REFERENCE_AIRSPEED, alpha=alpha)


def _scalar(value) -> float:
    """AeroSandbox returns arrays even for a single operating point."""
    return float(np.asarray(value).ravel()[0])


def _flat_plate_area(airplane: asb.Airplane) -> float:
    """Profile drag of a shape, expressed as an equivalent flat plate area."""
    point = _operating_point(0.0)
    aero = asb.AeroBuildup(airplane=airplane, op_point=point).run()
    return _scalar(aero["D_profile"]) / _scalar(point.dynamic_pressure())


def _part_airplane(name: str, wings=(), fuselages=()) -> asb.Airplane:
    return asb.Airplane(
        name=name,
        xyz_ref=[0.0, 0.0, 0.0],
        wings=list(wings),
        fuselages=list(fuselages),
    )


def _parabolic_fit(lift: np.ndarray, drag: np.ndarray) -> tuple[float, float]:
    basis = np.vstack([np.ones_like(lift), lift**2]).T
    zero_lift, induced = np.linalg.lstsq(basis, drag, rcond=None)[0]
    return float(zero_lift), float(induced)


def assembly_polar(configuration: Configuration) -> tuple[float, float]:
    """Fitted CD0 and k for a whole assembled aircraft."""
    aero = asb.AeroBuildup(
        airplane=airplane_for(configuration),
        op_point=_operating_point(POLAR_ALPHAS),
    ).run()
    return _parabolic_fit(np.asarray(aero["CL"]), np.asarray(aero["CD"]))


def neutral_point(configuration: Configuration) -> float:
    """Station at which pitching moment stops depending on lift.

    Taken from the slope of the moment curve about a known reference, which
    is the definition rather than an approximation of it.
    """
    airplane = airplane_for(configuration)
    aero = asb.AeroBuildup(
        airplane=airplane, op_point=_operating_point(np.array([-1.0, 1.0]))
    ).run()

    lift = np.asarray(aero["CL"])
    moment = np.asarray(aero["Cm"])
    slope = (moment[1] - moment[0]) / (lift[1] - lift[0])

    return float(airplane.xyz_ref[0] - slope * airplane.c_ref)


def maximum_lift_coefficient(wing: Wing) -> float:
    """Wing CL max, from the aerofoil's own stall with a finite-wing penalty."""
    aerofoil = asb.Airfoil(wing.airfoil.replace(" ", "").lower())
    reynolds = (
        AIR.density() * REFERENCE_AIRSPEED * wing.mean_aerodynamic_chord / AIR.dynamic_viscosity()
    )

    section = aerofoil.get_aero_from_neuralfoil(
        alpha=STALL_ALPHAS, Re=float(reynolds), mach=REFERENCE_AIRSPEED / 340.0
    )
    return float(np.asarray(section["CL"]).max()) * THREE_DIMENSIONAL_LIFT_FACTOR


def clean_drag_areas(catalog: Catalog) -> dict[str, float]:
    """Clean profile drag per part, scaled so the parts sum to the assembly.

    Each part is modelled alone, which misses the interference between them.
    Scaling to the assembled total puts that interference back, shared out in
    proportion to how draggy each part is on its own.
    """
    reference = Configuration(
        fuselage=catalog.fuselage,
        engine=catalog.engine,
        wing=catalog.wings[0],
        empennage=catalog.empennages[0],
        tail_extension=0.0,
        fuel_mass=0.3,
        payload_mass=4.0,
    )

    alone = {
        f"wing:{wing.name}": _flat_plate_area(
            _part_airplane(wing.name, wings=[main_wing_of(wing)])
        )
        for wing in catalog.wings
    }
    alone.update(
        {
            f"empennage:{empennage.name}": _flat_plate_area(
                _part_airplane(
                    empennage.name,
                    wings=[horizontal_tail_of(empennage, 0.0), vertical_tail_of(empennage, 0.0)],
                )
            )
            for empennage in catalog.empennages
        }
    )
    alone["fuselage"] = _flat_plate_area(
        _part_airplane(catalog.fuselage.name, fuselages=[body_of(reference)])
    )

    assembled_cd0, _ = assembly_polar(reference)
    assembled_area = assembled_cd0 * reference.wing.reference_area
    parts_total = (
        alone[f"wing:{reference.wing.name}"]
        + alone[f"empennage:{reference.empennage.name}"]
        + alone["fuselage"]
    )
    interference = assembled_area / parts_total

    return {name: area * interference for name, area in alone.items()}


def oswald_efficiencies(catalog: Catalog) -> dict[str, float]:
    """Span efficiency per wing, measured on the assembled aircraft."""
    efficiencies = {}
    for wing in catalog.wings:
        configuration = Configuration(
            fuselage=catalog.fuselage,
            engine=catalog.engine,
            wing=wing,
            empennage=catalog.empennages[0],
            tail_extension=0.0,
            fuel_mass=0.3,
            payload_mass=4.0,
        )
        _, induced_factor = assembly_polar(configuration)
        efficiencies[wing.name] = 1.0 / (np.pi * wing.aspect_ratio * induced_factor)
    return efficiencies


def neutral_point_table(catalog: Catalog) -> list[dict]:
    """Neutral point against tail extension, for every pairing."""
    table = []
    for wing, empennage in itertools.product(catalog.wings, catalog.empennages):
        stations = []
        for extension in EXTENSION_SAMPLES:
            configuration = Configuration(
                fuselage=catalog.fuselage,
                engine=catalog.engine,
                wing=wing,
                empennage=empennage,
                tail_extension=extension,
                fuel_mass=0.3,
                payload_mass=4.0,
            )
            stations.append(round(neutral_point(configuration), 5))

        table.append(
            {
                "wing": wing.name,
                "empennage": empennage.name,
                "tail_extension_m": list(EXTENSION_SAMPLES),
                "neutral_point_station_m": stations,
            }
        )
    return table


def _rewrite(path: Path, update) -> None:
    document = json.loads(path.read_text(encoding="utf-8"))
    update(document)
    document["_generated"] = "aerodynamic fields written by tools/generate_parts.py"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    catalog = load_catalog(PARTS_DIRECTORY)

    print("Running AeroSandbox over the catalogue...")
    drag = clean_drag_areas(catalog)
    efficiency = oswald_efficiencies(catalog)
    lift = {wing.name: maximum_lift_coefficient(wing) for wing in catalog.wings}

    def update_wings(document):
        for entry in document["wings"]:
            entry["clean_flat_plate_area_m2"] = round(drag[f"wing:{entry['name']}"], 6)
            entry["oswald_efficiency"] = round(efficiency[entry["name"]], 4)
            entry["max_lift_coefficient"] = round(lift[entry["name"]], 3)

    def update_empennages(document):
        for entry in document["empennages"]:
            entry["clean_flat_plate_area_m2"] = round(drag[f"empennage:{entry['name']}"], 6)

    def update_fuselage(document):
        document["fuselage"]["clean_flat_plate_area_m2"] = round(drag["fuselage"], 6)

    _rewrite(PARTS_DIRECTORY / "wings.json", update_wings)
    _rewrite(PARTS_DIRECTORY / "empennages.json", update_empennages)
    _rewrite(PARTS_DIRECTORY / "fuselage.json", update_fuselage)

    (PARTS_DIRECTORY / "stability.json").write_text(
        json.dumps(
            {
                "_generated": "written by tools/generate_parts.py",
                "neutral_points": neutral_point_table(catalog),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("\nclean flat plate areas (m2):")
    for name, area in sorted(drag.items()):
        print(f"  {name:24}{area:9.5f}")
    print("\noswald efficiency:")
    for name, value in sorted(efficiency.items()):
        print(f"  {name:24}{value:9.4f}")
    print("\nwing CL max:")
    for name, value in sorted(lift.items()):
        print(f"  {name:24}{value:9.3f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
