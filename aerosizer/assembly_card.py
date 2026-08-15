"""Rendering a recommendation as an assembly card.

This module is the display edge. It is the only place in the package that
converts out of SI, and the only place that decides how a number is worded.
It renders to plain text and imports no UI framework, so the same card can be
printed to a terminal, and later handed to Streamlit.

Lines are ordered by the sequence a pilot performs them in -- fit the wings,
fit the tail, set the boom, fuel it, balance it -- not by how interesting the
numbers are.
"""

from __future__ import annotations

from aerosizer.config import Fidelity, Recommendation, Requirements
from aerosizer.fuel import volume_for_mass
from aerosizer.units import (
    cubic_metres_to_litres,
    format_duration,
    metres_to_millimetres,
)

CARD_WIDTH = 62
LABEL_WIDTH = 18

FIDELITY_BANNER = {
    Fidelity.PLACEHOLDER: (
        "PLACEHOLDER PHYSICS - NOT FOR FLIGHT",
        "These numbers are structural stand-ins, not predictions. No",
        "flyability gate is applied yet. Do not build from this card.",
    ),
    Fidelity.PRELIMINARY: (
        "PRELIMINARY PHYSICS",
        "Real formulae, provisional coefficients. Treat predictions as",
        "indicative and verify balance on the ground before flight.",
    ),
    Fidelity.VALIDATED: (
        "SIZING AID ONLY",
        "This tool is a sizing and prediction aid. It is not an",
        "airworthiness approval and confers no flight clearance.",
    ),
}


def render_assembly_card(recommendation: Recommendation) -> str:
    """Render the recommendation as the card a pilot builds from."""
    sections = [
        _render_heading(recommendation.requirements),
        _render_assembly_steps(recommendation),
        _render_prediction(recommendation),
        _render_banner(recommendation),
    ]
    return "\n".join(sections)


def _render_heading(requirements: Requirements) -> str:
    mission = " · ".join(
        [
            requirements.mode.value.replace("_", " ").title(),
            format_duration(requirements.duration),
            f"{requirements.payload_mass:.1f} kg payload",
        ]
    )
    return "\n".join(
        [
            "=" * CARD_WIDTH,
            "  ASSEMBLY CARD",
            f"  {mission}",
            "=" * CARD_WIDTH,
        ]
    )


def _render_assembly_steps(recommendation: Recommendation) -> str:
    configuration = recommendation.configuration
    results = recommendation.results

    fuel_volume = volume_for_mass(configuration.fuel_mass)
    fuel_instruction = (
        f"{cubic_metres_to_litres(fuel_volume):.1f} L  ({configuration.fuel_mass:.1f} kg)"
    )

    return "\n".join(
        [
            _line("Wings", configuration.wing.name),
            _line("Empennage", configuration.empennage.name),
            _line(
                "Tail extension",
                f"{metres_to_millimetres(configuration.tail_extension):.0f} mm",
            ),
            _line("Fuel fill", fuel_instruction),
            _line(
                "CG target",
                f"{metres_to_millimetres(results.centre_of_gravity_station):.0f} mm from nose",
            ),
        ]
    )


def _render_prediction(recommendation: Recommendation) -> str:
    results = recommendation.results
    prediction = " · ".join(
        [
            format_duration(results.endurance),
            f"{results.stall_speed:.1f} m/s stall",
            f"SM {results.static_margin * 100.0:.0f}%",
        ]
    )
    return "\n".join(
        [
            "-" * CARD_WIDTH,
            _line("Predicted", prediction),
            "",
            f"  {recommendation.rationale}",
        ]
    )


def _render_banner(recommendation: Recommendation) -> str:
    headline, *detail = FIDELITY_BANNER[recommendation.results.fidelity]
    lines = ["=" * CARD_WIDTH, f"  ** {headline} **"]
    lines.extend(f"  {sentence}" for sentence in detail)
    lines.append("=" * CARD_WIDTH)
    return "\n".join(lines)


def _line(label: str, value: str) -> str:
    return f"  {label.ljust(LABEL_WIDTH)}{value}"
