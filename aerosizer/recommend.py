"""The product: state a mission, get told what to build.

``recommend`` is where every inversion in this project lives. It enumerates
the catalogue, evaluates each combination through ``analyze``, and ranks the
results under the pilot's chosen mode.

The search is deliberately exhaustive. Four wings by three empennages is
twelve combinations, and a Raspberry Pi evaluates all of them in
milliseconds -- so there is no optimiser here, no heuristic search and no
cached answer table. Enumerate, then rank.

BUILD STATE -- B1
=================
Two things this function will eventually solve for are currently fixed:

    fuel mass       held at a placeholder; the sizing loop arrives at T1,
                    at which point the pilot's requested duration starts
                    to matter
    tail extension  held fully retracted; bisection on static margin
                    arrives at T2

There is also no flyability gate yet, so this will happily recommend a
combination that cannot be trimmed or cannot climb. That gate lands at T3 and
must be in place before anyone builds hardware from this output.
"""

from __future__ import annotations

import itertools

from aerosizer.analyze import analyze
from aerosizer.config import Candidate, Configuration, Recommendation, Requirements
from aerosizer.parts import Catalog
from aerosizer.ranking import explain_choice, figure_of_merit, rank_candidates

# Replaced by the fuel sizing loop at T1.
PLACEHOLDER_FUEL_MASS = 2.0

# Replaced by bisection on static margin at T2.
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
    """Analyse every wing and empennage pairing in the catalogue."""
    candidates = []
    for wing, empennage in itertools.product(catalog.wings, catalog.empennages):
        configuration = Configuration(
            fuselage=catalog.fuselage,
            engine=catalog.engine,
            wing=wing,
            empennage=empennage,
            tail_extension=PLACEHOLDER_TAIL_EXTENSION,
            fuel_mass=PLACEHOLDER_FUEL_MASS,
            payload_mass=requirements.payload_mass,
        )
        results = analyze(configuration)
        candidates.append(
            Candidate(
                configuration=configuration,
                results=results,
                figure_of_merit=figure_of_merit(results),
            )
        )
    return tuple(candidates)
