"""Choosing between configurations.

There is one objective, and it is not mode-specific. Once the pilot has stated
a mission, every configuration capable of flying it will fly it -- they differ
only in what it costs:

    Complete this mission on the least fuel.

So ranking takes no mode. A mode decides which profile is flown and which
numbers the pilot is asked for, not what counts as better.

Ties are broken deterministically by part name, so the same request always
produces the same assembly card. Preferring the configuration with the greater
constraint margin -- the tie-break the plan actually calls for -- arrives with
the flyability gate, since there are no constraints to have margin against
until then.
"""

from __future__ import annotations

from aerosizer.config import Candidate, FlightLog
from aerosizer.units import format_mass


def figure_of_merit(flight: FlightLog) -> float:
    """Score a configuration on the mission it was asked to fly.

    Higher is better, so the fuel burned is negated: the cheapest way to
    complete the stated mission wins.
    """
    return -flight.total_fuel


def rank_candidates(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    """Order candidates best first, breaking ties deterministically."""
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                -candidate.figure_of_merit,
                candidate.configuration.wing.name,
                candidate.configuration.empennage.name,
            ),
        )
    )


def explain_choice(chosen: Candidate, runner_up: Candidate | None) -> str:
    """One line of reasoning: why this one, and what it beat."""
    reason = "Chosen for the lowest fuel burn."
    if runner_up is None:
        return reason

    alternative = f"{runner_up.configuration.wing.name} + {runner_up.configuration.empennage.name}"
    extra = runner_up.flight.total_fuel - chosen.flight.total_fuel
    return f"{reason} Next best: {alternative}, {format_mass(extra)} more."
