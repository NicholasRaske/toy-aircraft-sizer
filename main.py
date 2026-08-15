"""Command-line entry point: state a mission, get an assembly card.

This is the deliberately ugly text interface. It exists so that the loop from
requirements to a printed card closes end to end, while schema problems are
still cheap to fix. The kiosk calls exactly the same functions.

Its arguments are built from whichever fields the chosen mode declares, so a
new mode becomes usable here the moment it exists.

    python main.py --mode loiter --transit-distance 12 --station-time 90
    python main.py --mode return_range --distance 40 --payload 3
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aerosizer import (
    CatalogError,
    FlightMode,
    InputField,
    Quantity,
    Requirements,
    input_fields,
    load_catalog,
    mission_from,
    recommend,
    render_assembly_card,
)
from aerosizer.units import kilometres_to_metres, minutes_to_seconds

DEFAULT_PARTS_DIRECTORY = Path(__file__).parent / "parts"

# The command line takes the units a pilot would say out loud and converts
# once, on the way in. Everything past this point is SI.
ARGUMENT_UNIT: dict[Quantity, tuple[str, float]] = {
    Quantity.DISTANCE: ("km", kilometres_to_metres(1.0)),
    Quantity.DURATION: ("min", minutes_to_seconds(1.0)),
    Quantity.MASS: ("kg", 1.0),
}


def main() -> int:
    arguments = _parse_arguments()

    try:
        catalog = load_catalog(arguments.parts)
    except CatalogError as error:
        print(f"Could not load the part catalogue: {error}")
        return 1

    mode = FlightMode(arguments.mode)
    values = {
        field.key: getattr(arguments, field.key) * _si_per_display_unit(field)
        for field in input_fields(mode)
    }

    requirements = Requirements(
        mission=mission_from(mode, values),
        payload_mass=values["payload_mass"],
    )

    print(render_assembly_card(recommend(requirements, catalog)))
    return 0


def _parse_arguments() -> argparse.Namespace:
    """Two passes: the mode decides which other arguments exist."""
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--mode",
        choices=[mode.value for mode in FlightMode],
        default=FlightMode.LOITER.value,
        help="The shape of the sortie.",
    )
    shared.add_argument(
        "--parts",
        type=Path,
        default=DEFAULT_PARTS_DIRECTORY,
        help="Directory holding the part catalogue.",
    )
    chosen, _ = shared.parse_known_args()

    parser = argparse.ArgumentParser(
        parents=[shared],
        description="Recommend how to assemble the aircraft for a stated mission.",
    )
    for field in input_fields(FlightMode(chosen.mode)):
        unit_name, si_per_unit = ARGUMENT_UNIT[field.quantity]
        parser.add_argument(
            f"--{field.key.replace('_', '-')}",
            dest=field.key,
            type=float,
            default=field.default / si_per_unit,
            help=f"{field.label.title()}, in {unit_name}.",
        )
    return parser.parse_args()


def _si_per_display_unit(field: InputField) -> float:
    _, si_per_unit = ARGUMENT_UNIT[field.quantity]
    return si_per_unit


if __name__ == "__main__":
    raise SystemExit(main())
