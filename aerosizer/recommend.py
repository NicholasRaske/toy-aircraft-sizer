"""The product: state a mission, get told what to build.

``recommend`` is where every inversion in this project lives. It enumerates
the catalogue, evaluates each combination through ``analyze``, and ranks the
results under the pilot's chosen mode.

The search is deliberately exhaustive. Four wings by three empennages is
twelve combinations, and a Raspberry Pi evaluates all of them in
milliseconds -- so there is no optimiser here, no heuristic search and no
cached answer table. Enumerate, then rank.

BUILD STATE -- phase 2, step 6
==============================
Fuel is now sized for the stated mission rather than assumed. Tail extension
is still held fully retracted; bisection on static margin is the next phase.

There is also no flyability gate yet, so this will happily recommend a
combination that cannot be trimmed. That gate must be in place before anyone
builds hardware from this output.
"""

from __future__ import annotations

import itertools
from dataclasses import replace

from aerosizer.analyze import analyze
from aerosizer.atmosphere import atmosphere_at
from aerosizer.config import Candidate, Configuration, Recommendation, Requirements
from aerosizer.fuel import size_fuel
from aerosizer.parts import Catalog
from aerosizer.ranking import explain_choice, figure_of_merit, rank_candidates

# Replaced by bisection on static margin next phase.
PLACEHOLDER_TAIL_EXTENSION = 0.0


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
            tail_extension=PLACEHOLDER_TAIL_EXTENSION,
            fuel_mass=0.0,
            payload_mass=requirements.payload_mass,
        )

        fuel = size_fuel(unfuelled, profile, atmosphere)
        configuration = replace(unfuelled, fuel_mass=fuel.mass)

        candidates.append(
            Candidate(
                configuration=configuration,
                results=analyze(configuration, atmosphere),
                flight=fuel.flight,
                figure_of_merit=figure_of_merit(fuel.flight),
            )
        )
    return tuple(candidates)
