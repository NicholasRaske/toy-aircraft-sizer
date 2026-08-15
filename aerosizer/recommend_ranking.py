"""Choosing between flyable configurations.

The mode the pilot picks decides what "better" means. Every mode is expressed
as a figure of merit where **higher is always better**, so that ranking itself
never has to know which way round a given metric runs.

Ties are broken deterministically by part name, so the same request always
produces the same assembly card. Preferring the configuration with the greater
constraint margin -- the tie-break the plan actually calls for -- arrives with
the flyability gate at T3, since there are no constraints to have margin
against until then.
"""

from __future__ import annotations

from aerosizer.config import Candidate, FlightMode, Results
from aerosizer.units import format_duration

OBJECTIVE_DESCRIPTION = {
    FlightMode.LOITER: "endurance",
    FlightMode.RANGE: "still-air range",
    FlightMode.SPEED: "top speed",
    FlightMode.SHORT_FIELD: "the lowest stall speed",
}


def figure_of_merit(mode: FlightMode, results: Results) -> float:
    """Score a result under a mode. Higher is better, always."""
    match mode:
        case FlightMode.LOITER:
            return results.endurance
        case FlightMode.RANGE:
            return results.still_air_range
        case FlightMode.SPEED:
            return results.max_level_speed
        case FlightMode.SHORT_FIELD:
            return -results.stall_speed
    raise ValueError(f"No figure of merit defined for mode {mode}")


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


def explain_choice(
    mode: FlightMode,
    chosen: Candidate,
    runner_up: Candidate | None,
) -> str:
    """One line of reasoning: why this one, and what it beat."""
    reason = f"Chosen for {OBJECTIVE_DESCRIPTION[mode]}."
    if runner_up is None:
        return reason

    runner_up_name = (
        f"{runner_up.configuration.wing.name} + {runner_up.configuration.empennage.name}"
    )
    return f"{reason} Next best: {runner_up_name}, {_describe_shortfall(mode, chosen, runner_up)}."


def _describe_shortfall(mode: FlightMode, chosen: Candidate, runner_up: Candidate) -> str:
    """How much worse the runner-up is, in the units of the chosen mode."""
    chosen_results = chosen.results
    runner_up_results = runner_up.results

    match mode:
        case FlightMode.LOITER:
            shortfall = chosen_results.endurance - runner_up_results.endurance
            return f"{format_duration(shortfall)} shorter"
        case FlightMode.RANGE:
            shortfall = chosen_results.still_air_range - runner_up_results.still_air_range
            return f"{shortfall / 1000.0:.1f} km shorter"
        case FlightMode.SPEED:
            shortfall = chosen_results.max_level_speed - runner_up_results.max_level_speed
            return f"{shortfall:.1f} m/s slower"
        case FlightMode.SHORT_FIELD:
            excess = runner_up_results.stall_speed - chosen_results.stall_speed
            return f"{excess:.1f} m/s faster stall"
    raise ValueError(f"No shortfall description defined for mode {mode}")
