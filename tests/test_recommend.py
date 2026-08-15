"""Properties of the recommender.

Like the forward-model tests, these are written to survive every change of
fidelity underneath them. They assert that the recommender enumerates
honestly, chooses consistently, and never returns nothing.

The most important test in the eventual suite -- that no recommendation ever
violates a flyability rule -- cannot be written yet, because there is no gate.
Its absence is the reason the assembly card carries a not-for-flight banner.
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
from aerosizer.assembly_card import build_assembly_card


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


def test_a_recommendation_is_always_returned(catalog):
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


def test_the_chosen_configuration_burns_the_least_fuel(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    cheapest = min(candidate.flight.total_fuel for candidate in recommendation.considered)
    assert recommendation.chosen.flight.total_fuel == pytest.approx(cheapest)


def test_identical_requests_produce_identical_cards(catalog, loiter_requirements):
    first = render_assembly_card(recommend(loiter_requirements, catalog))
    second = render_assembly_card(recommend(loiter_requirements, catalog))

    assert first == second


def test_loiter_prefers_the_efficient_wing(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    assert recommendation.configuration.wing.name == "Surveyor"


def test_every_mode_is_ranked_the_same_way(catalog):
    """A mode selects the profile flown, not what counts as better.

    All three are ranked on the fuel needed to complete the stated mission, so
    they cannot disagree about which configuration is most efficient.
    """
    chosen = {
        recommend(_requirements_for(mode), catalog).configuration.wing.name
        for mode in FlightMode
    }

    assert len(chosen) == 1


def test_the_recommended_fuel_completes_the_mission(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    assert recommendation.chosen.flight.completed
    assert recommendation.configuration.fuel_mass > 0.0


def test_a_longer_mission_is_given_more_fuel(catalog, loiter_requirements):
    from dataclasses import replace

    from aerosizer.mission import LoiterMission

    short = recommend(loiter_requirements, catalog).configuration.fuel_mass
    longer = replace(
        loiter_requirements,
        mission=LoiterMission(transit_distance=10_000.0, station_time=4 * 3600.0),
    )

    assert recommend(longer, catalog).configuration.fuel_mass > short


def test_rationale_names_the_runner_up(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)

    assert recommendation.runner_up is not None
    assert recommendation.runner_up.configuration.wing.name in recommendation.rationale


def test_card_carries_the_assembly_instructions(catalog, loiter_requirements):
    """Every instruction in the card data must survive into the rendered text.

    Derived from the card rather than duplicating its labels, so the exact
    wording is pinned in one place only.
    """
    recommendation = recommend(loiter_requirements, catalog)
    text = render_assembly_card(recommendation)

    for entry in build_assembly_card(recommendation).assembly:
        assert entry.label in text
        assert entry.value in text


def test_card_states_how_far_the_physics_can_be_trusted(catalog, loiter_requirements):
    card = render_assembly_card(recommend(loiter_requirements, catalog))

    assert "PRELIMINARY PHYSICS" in card
