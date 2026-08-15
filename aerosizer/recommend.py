"""The product: state a mission, get told what to build.

``recommend`` is where every inversion in this project lives. It enumerates
the catalogue, evaluates each combination through ``analyze``, and ranks the
results under the pilot's chosen mode.

The search is deliberately exhaustive. Four wings by three empennages is
twelve combinations, and a Raspberry Pi evaluates all of them in
milliseconds -- so there is no optimiser here, no heuristic search and no
cached answer table. Enumerate, then rank.

BUILD STATE -- phase 2 complete
===============================
Fuel is sized for the stated mission and the tail is trimmed to a target
static margin. There is still no flyability gate, so this will recommend a
combination that is badly out of balance rather than excluding it. That gate
must be in place before anyone builds hardware from this output.
"""

from __future__ import annotations

import itertools
from dataclasses import replace

from aerosizer.analyze import analyze
from aerosizer.atmosphere import atmosphere_at
from aerosizer.config import Candidate, Configuration, Recommendation, Requirements
from aerosizer.fuel import size_fuel
from aerosizer.mass import mass_properties
from aerosizer.parts import Catalog
from aerosizer.ranking import explain_choice, figure_of_merit, rank_candidates
from aerosizer.stability import balance_of, solve_tail_extension


def recommend(requirements: Requirements, catalog: Catalog) -> Recommendation:
    """Choose the configuration that best meets the stated mission."""
    ranked = rank_candidates(_evaluate_every_combination(requirements, catalog))

    chosen = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None

    return Recommendation(
        requirements=requirements,
        considered=ranked,
        rationale=explain_choice(chosen, runner_up),
    )


def _trimmed(configuration: Configuration) -> Configuration:
    """Set the boom to the extension that trims this loading.

    Solved at takeoff mass, which is the critical case: the tank sits aft of
    the balance point, so a full one carries the centre of gravity aft and
    leaves the least margin.
    """
    boom = configuration.fuselage.tail_boom

    def margin_at(extension: float) -> float:
        trial = replace(configuration, tail_extension=extension)
        return balance_of(trial, mass_properties(trial)).static_margin

    solved = solve_tail_extension(margin_at, boom.max_extension)
    return replace(configuration, tail_extension=boom.quantise(solved))


def _evaluate_every_combination(
    requirements: Requirements,
    catalog: Catalog,
) -> tuple[Candidate, ...]:
    """Fly every wing and empennage pairing over the stated mission."""
    atmosphere = atmosphere_at(requirements.field_elevation, requirements.field_temperature)
    profile = requirements.profile

    candidates = []
    for wing, empennage in itertools.product(catalog.wings, catalog.empennages):
        unfuelled = Configuration(
            fuselage=catalog.fuselage,
            engine=catalog.engine,
            wing=wing,
            empennage=empennage,
            neutral_point_curve=catalog.neutral_point_curve(wing, empennage),
            tail_extension=0.0,
            fuel_mass=0.0,
            payload_mass=requirements.payload_mass,
        )

        fuel = size_fuel(unfuelled, profile, atmosphere)
        configuration = _trimmed(replace(unfuelled, fuel_mass=fuel.mass))

        candidates.append(
            Candidate(
                configuration=configuration,
                results=analyze(configuration, atmosphere),
                flight=fuel.flight,
                figure_of_merit=figure_of_merit(fuel.flight),
            )
        )
    return tuple(candidates)
