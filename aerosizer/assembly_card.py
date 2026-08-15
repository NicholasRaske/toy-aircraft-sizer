"""The assembly card: what the pilot is told to do.

This module is the display edge. It is the only place in the package that
converts out of SI, and the only place that decides how a number is worded.

It produces **structured** card data. Rendering that structure to plain text is
one consumer, provided here; a kiosk screen is another. Keeping the structure
separate from any one presentation means every interface shares the same
decisions about units, wording and severity, and no interface has to make
judgements of its own. An interface should hold layout and event plumbing,
nothing else.

Lines are ordered by the sequence a pilot performs them in -- fit the wings,
fit the tail, set the boom, fuel it, balance it -- not by how interesting the
numbers are.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aerosizer.config import Fidelity, Recommendation, Requirements, Results
from aerosizer.fuel import volume_for_mass
from aerosizer.mission import InputField, Quantity, mission_fields
from aerosizer.units import (
    cubic_metres_to_litres,
    format_distance,
    format_duration,
    format_mass,
    format_speed,
    metres_to_millimetres,
)

# The one place that decides how each kind of number is worded. Every
# interface formats through this, so none of them can disagree.
QUANTITY_FORMAT = {
    Quantity.DISTANCE: format_distance,
    Quantity.DURATION: format_duration,
    Quantity.MASS: format_mass,
}


def format_quantity(quantity: Quantity, value: float) -> str:
    return QUANTITY_FORMAT[quantity](value)


def format_field(field: InputField, value: float) -> str:
    return format_quantity(field.quantity, value)


class BannerSeverity(Enum):
    """How loudly an interface should say this.

    Severity is decided here rather than by each interface, so that a kiosk
    screen and a printed card can never disagree about whether something is a
    warning.
    """

    CRITICAL = "critical"
    CAUTION = "caution"
    INFORMATION = "information"


@dataclass(frozen=True)
class CardEntry:
    """One instruction: a thing to fit or set, and the value to set it to."""

    label: str
    value: str
    detail: str | None = None


@dataclass(frozen=True)
class CardBanner:
    """The standing caveat, worded for the current level of fidelity."""

    headline: str
    detail: tuple[str, ...]
    severity: BannerSeverity


@dataclass(frozen=True)
class AssemblyCard:
    """Everything an interface needs to show, already in display units.

    Two sections, because they answer different questions. ``assembly`` is
    what to build; ``speeds`` is what the result will do once it is flying.
    Both are the same shape, so one renderer draws either.
    """

    mission: tuple[str, ...]
    assembly: tuple[CardEntry, ...]
    speeds: tuple[CardEntry, ...]
    prediction: tuple[str, ...]
    rationale: str
    banner: CardBanner


BANNERS = {
    Fidelity.PLACEHOLDER: CardBanner(
        headline="PLACEHOLDER PHYSICS - NOT FOR FLIGHT",
        detail=(
            "These numbers are structural stand-ins, not predictions. No",
            "flyability gate is applied yet. Do not build from this card.",
        ),
        severity=BannerSeverity.CRITICAL,
    ),
    Fidelity.PRELIMINARY: CardBanner(
        headline="PRELIMINARY PHYSICS",
        detail=(
            "Real formulae, provisional coefficients. Treat predictions as",
            "indicative and verify balance on the ground before flight.",
        ),
        severity=BannerSeverity.CAUTION,
    ),
    Fidelity.VALIDATED: CardBanner(
        headline="SIZING AID ONLY",
        detail=(
            "This tool is a sizing and prediction aid. It is not an",
            "airworthiness approval and confers no flight clearance.",
        ),
        severity=BannerSeverity.INFORMATION,
    ),
}


def build_assembly_card(recommendation: Recommendation) -> AssemblyCard:
    """Turn a recommendation into display-ready card data."""
    configuration = recommendation.configuration
    results = recommendation.results
    flight = recommendation.chosen.flight
    fuel_volume = volume_for_mass(configuration.fuel_mass)

    assembly = (
        CardEntry("Wings", configuration.wing.name),
        CardEntry("Empennage", configuration.empennage.name),
        CardEntry(
            "Tail extension",
            f"{metres_to_millimetres(configuration.tail_extension):.0f} mm",
        ),
        # Deliberately not "fuel fill". There is no reserve in this figure;
        # it is what the mission burns and nothing more. A pilot who reads it
        # as a fill instruction runs a tank dry.
        CardEntry(
            "Mission fuel",
            f"{cubic_metres_to_litres(fuel_volume):.2f} L",
            f"{configuration.fuel_mass:.2f} kg",
        ),
        CardEntry(
            "CG target",
            f"{metres_to_millimetres(results.mass.centre_of_gravity_station):.0f} mm",
            "from nose",
        ),
    )

    prediction = (
        format_duration(flight.total_duration),
        f"{cubic_metres_to_litres(fuel_volume):.2f} L",
        f"{results.mass.all_up_mass:.1f} kg",
    )

    return AssemblyCard(
        mission=_describe_mission(recommendation.requirements),
        assembly=assembly,
        speeds=_describe_speeds(results),
        prediction=prediction,
        rationale=recommendation.rationale,
        banner=BANNERS[results.fidelity],
    )


def _describe_speeds(results: Results) -> tuple[CardEntry, ...]:
    """The speeds worth flying, each with whatever is limiting it.

    The limit is shown rather than implied, because several of these are set
    by stall margin rather than by the aerodynamic optimum they are named
    after, and a pilot reading the number deserves to know which.
    """
    envelope = results.envelope
    climb = results.climb

    return (
        CardEntry("Stall", format_speed(envelope.stall_speed), "at takeoff mass"),
        CardEntry(
            "Best endurance",
            format_speed(envelope.loiter_speed.value),
            envelope.loiter_speed.limited_by,
        ),
        CardEntry(
            "Best range",
            format_speed(envelope.cruise_speed.value),
            envelope.cruise_speed.limited_by,
        ),
        CardEntry(
            "Max level",
            format_speed(envelope.max_level_speed.value),
            envelope.max_level_speed.limited_by,
        ),
        CardEntry(
            "Best climb",
            f"{climb.best_rate:.1f} m/s up",
            f"at {climb.speed_for_best_rate.value:.0f} m/s",
        ),
    )


def _describe_mission(requirements: Requirements) -> tuple[str, ...]:
    """Read the mission back out through the fields the mode declared.

    Nothing here knows which mission it is holding, so a new mode describes
    itself without this function changing.
    """
    mode = requirements.mode
    described = [mode.value.replace("_", " ").title()]
    described.extend(
        f"{format_field(field, getattr(requirements.mission, field.key))} {field.label.lower()}"
        for field in mission_fields(mode)
    )
    described.append(f"{format_mass(requirements.payload_mass)} payload")
    return tuple(described)


CARD_WIDTH = 62
LABEL_WIDTH = 18


def render_assembly_card(recommendation: Recommendation) -> str:
    """Render the card as plain text, for the terminal and for printing."""
    card = build_assembly_card(recommendation)
    rule = "=" * CARD_WIDTH

    lines = [rule, "  ASSEMBLY CARD", f"  {' · '.join(card.mission)}", rule]
    lines.extend(_render_entry(entry) for entry in card.assembly)
    lines.append("-" * CARD_WIDTH)
    lines.extend(_render_entry(entry) for entry in card.speeds)
    lines.append("-" * CARD_WIDTH)
    lines.append(_render_line("Mission", " · ".join(card.prediction)))
    lines.append("")
    lines.append(f"  {card.rationale}")
    lines.append(rule)
    lines.append(f"  ** {card.banner.headline} **")
    lines.extend(f"  {sentence}" for sentence in card.banner.detail)
    lines.append(rule)

    return "\n".join(lines)


def _render_entry(entry: CardEntry) -> str:
    value = entry.value if entry.detail is None else f"{entry.value}  ({entry.detail})"
    return _render_line(entry.label, value)


def _render_line(label: str, value: str) -> str:
    return f"  {label.ljust(LABEL_WIDTH)}{value}"
