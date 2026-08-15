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

from dataclasses import replace

import pytest

from aerosizer import FlightMode, recommend, render_assembly_card


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
        recommendation = recommend(replace(loiter_requirements, mode=mode), catalog)

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


def test_speed_prefers_the_fast_wing(catalog, loiter_requirements):
    recommendation = recommend(replace(loiter_requirements, mode=FlightMode.SPEED), catalog)

    assert recommendation.configuration.wing.name == "Dash"


def test_short_field_prefers_the_lowest_stall_speed(catalog, loiter_requirements):
    recommendation = recommend(replace(loiter_requirements, mode=FlightMode.SHORT_FIELD), catalog)

    lowest_stall = min(
        candidate.results.stall_speed for candidate in recommendation.considered
    )
    assert recommendation.results.stall_speed == pytest.approx(lowest_stall)


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
