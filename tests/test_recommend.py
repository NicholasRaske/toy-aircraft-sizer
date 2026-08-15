"""Properties of the recommender.

Like the forward-model tests, these are written to survive every change of
fidelity underneath them. They assert that the recommender enumerates
honestly, chooses consistently, and never returns nothing.

The most important test in the eventual suite -- that no recommendation ever
violates a flyability rule -- cannot be written yet, because the gate arrives
at T3. Its absence is the reason the assembly card currently carries a
not-for-flight banner.
"""

from __future__ import annotations

import pytest

from aerosizer import (
    FlightMode,
    Requirements,
    default_values,
    mission_from,
    recommend,
    render_assembly_card,
)


def _requirements_for(mode: FlightMode, payload_mass: float = 4.0) -> Requirements:
    return Requirements(
        mission=mission_from(mode, default_values(mode)),
        payload_mass=payload_mass,
    )


def test_every_combination_is_considered_exactly_once(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    pairings = [
        (candidate.configuration.wing.name, candidate.configuration.empennage.name)
        for candidate in recommendation.considered
    ]

    assert len(pairings) == len(catalog.wings) * len(catalog.empennages)
    assert len(set(pairings)) == len(pairings)


def test_a_recommendation_is_always_returned(catalog, loiter_requirements):
    for mode in FlightMode:
        recommendation = recommend(_requirements_for(mode), catalog)

        assert recommendation.chosen is not None
        assert recommendation.rationale


def test_the_chosen_candidate_leads_the_ranking(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    best = max(candidate.figure_of_merit for candidate in recommendation.considered)
    assert recommendation.chosen.figure_of_merit == pytest.approx(best)


def test_ranking_is_ordered_best_first(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    scores = [candidate.figure_of_merit for candidate in recommendation.considered]
    assert scores == sorted(scores, reverse=True)


def test_identical_requests_produce_identical_cards(catalog, loiter_requirements):
    first = render_assembly_card(recommend(loiter_requirements, catalog))
    second = render_assembly_card(recommend(loiter_requirements, catalog))

    assert first == second


def test_loiter_prefers_the_efficient_wing(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    assert recommendation.configuration.wing.name == "Surveyor"


def test_every_mode_is_ranked_the_same_way(catalog, loiter_requirements):
    """A mode selects the profile flown, not what counts as better.

    All three are ranked on the fuel needed to complete the stated mission, so
    they cannot disagree about which configuration is most efficient.
    """
    chosen = {
        recommend(_requirements_for(mode), catalog).configuration.wing.name
        for mode in FlightMode
    }

    assert len(chosen) == 1


def test_rationale_names_the_runner_up(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    assert recommendation.runner_up is not None
    assert recommendation.runner_up.configuration.wing.name in recommendation.rationale


def test_card_carries_the_assembly_instructions(catalog, loiter_requirements):
    card = render_assembly_card(recommend(loiter_requirements, catalog))

    for expected_line in ("Wings", "Empennage", "Tail extension", "Fuel fill", "CG target"):
        assert expected_line in card


def test_card_refuses_to_hide_placeholder_physics(catalog, loiter_requirements):
    card = render_assembly_card(recommend(loiter_requirements, catalog))

    assert "NOT FOR FLIGHT" in card
