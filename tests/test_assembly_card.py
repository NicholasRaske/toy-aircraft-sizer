"""The card is structured data; text is only one way of showing it.

These tests cover the display edge itself -- units, wording and severity --
because that is the layer every interface shares. The widget layer on top of
it gets a smoke test and nothing more.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from aerosizer import Fidelity, recommend, render_assembly_card
from aerosizer.assembly_card import (
    BANNERS,
    BannerSeverity,
    build_assembly_card,
)
from aerosizer.assembly_card import (
    render_assembly_card as render_from_module,
)


@pytest.fixture
def card(catalog, loiter_requirements):
    return build_assembly_card(recommend(loiter_requirements, catalog))


def test_card_is_ordered_by_assembly_sequence(card):
    labels = [entry.label for entry in card.assembly]

    assert labels == ["Wings", "Empennage", "Tail extension", "Fuel fill", "CG target"]


def test_mission_is_described_in_pilot_units(card):
    assert card.mission == (
        "Loiter",
        "10.0 km to site",
        "1 h 00 min on station",
        "4.0 kg payload",
    )


def test_fuel_is_instructed_as_a_volume(card):
    fuel = next(entry for entry in card.assembly if entry.label == "Fuel fill")

    # The pilot fills a tank, so volume leads and mass is the supporting detail.
    assert fuel.value.endswith(" L")
    assert fuel.detail is not None and fuel.detail.endswith(" kg")


def test_lengths_are_shown_in_millimetres(card):
    for label in ("Tail extension", "CG target"):
        entry = next(entry for entry in card.assembly if entry.label == label)
        assert entry.value.endswith(" mm")


def test_placeholder_physics_is_flagged_as_critical(card):
    assert card.banner.severity is BannerSeverity.CRITICAL
    assert "NOT FOR FLIGHT" in card.banner.headline


def test_every_fidelity_level_has_a_banner():
    # A missing banner would mean an interface silently showing nothing at the
    # moment the tool most needs to caveat itself.
    for fidelity in Fidelity:
        assert fidelity in BANNERS
        assert BANNERS[fidelity].headline


def test_text_rendering_contains_every_card_entry(catalog, loiter_requirements):
    recommendation = recommend(loiter_requirements, catalog)
    card = build_assembly_card(recommendation)
    text = render_assembly_card(recommendation)

    for entry in card.assembly:
        assert entry.label in text
        assert entry.value in text
    assert card.banner.headline in text


def test_package_export_matches_the_module_function():
    assert render_assembly_card is render_from_module


def test_payload_change_is_reflected_in_the_mission(catalog, loiter_requirements):
    heavier = replace(loiter_requirements, payload_mass=6.5)
    card = build_assembly_card(recommend(heavier, catalog))

    assert "6.5 kg payload" in card.mission
