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

from aerosizer.config import Candidate, Results


def figure_of_merit(results: Results) -> float:
    """Score a configuration. Higher is better.

    The real objective is fuel burned over the stated mission, which needs
    ``fly`` (step 5). Until then lift-to-drag stands in for it: a more
    efficient aircraft burns less over the same route. Directionally right,
    and replaced by the real figure at step 6.
    """
    return results.lift_to_drag_max


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
    """One line of reasoning: why this one, and what it beat.

    The fuel difference against the runner-up belongs here and arrives with
    the mission model. Until then the line names the alternative without
    quantifying the gap, rather than quoting a number that is not yet real.
    """
    reason = "Chosen as the most efficient of the available combinations."
    if runner_up is None:
        return reason

    alternative = f"{runner_up.configuration.wing.name} + {runner_up.configuration.empennage.name}"
    return f"{reason} Next best: {alternative}."
