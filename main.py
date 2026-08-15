"""Command-line entry point: state a mission, get an assembly card.

This is the deliberately ugly text interface. It exists so that the loop from
requirements to a printed card closes end to end before any UI exists, while
schema problems are still cheap to fix. The Streamlit app arrives at T6 and
will call exactly the same two functions.

    python main.py --mode loiter --duration 1.0 --payload 4.0
"""

from __future__ import annotations

import argparse
from pathlib import Path

from aerosizer import (
    CatalogError,
    FlightMode,
    Requirements,
    load_catalog,
    recommend,
    render_assembly_card,
)
from aerosizer.units import hours_to_seconds

DEFAULT_PARTS_DIRECTORY = Path(__file__).parent / "parts"


def main() -> int:
    arguments = _parse_arguments()

    try:
        catalog = load_catalog(arguments.parts)
    except CatalogError as error:
        print(f"Could not load the part catalogue: {error}")
        return 1

    requirements = Requirements(
        mode=FlightMode(arguments.mode),
        duration=hours_to_seconds(arguments.duration),
        payload_mass=arguments.payload,
    )

    print(render_assembly_card(recommend(requirements, catalog)))
    return 0


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recommend how to assemble the aircraft for a stated mission.",
    )
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in FlightMode],
        default=FlightMode.LOITER.value,
        help="What the flight is optimised for.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=1.0,
        help="Requested flight duration, in hours.",
    )
    parser.add_argument(
        "--payload",
        type=float,
        default=4.0,
        help="Payload mass, in kilograms.",
    )
    parser.add_argument(
        "--parts",
        type=Path,
        default=DEFAULT_PARTS_DIRECTORY,
        help="Directory holding the part catalogue.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
