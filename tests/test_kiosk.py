"""Smoke tests for the kiosk screen.

The widget layer is deliberately thin, so it is deliberately barely tested.
What matters is that it builds, that it survives every interaction, that it
holds no state of its own, and that it never branches on the mode. Everything
else worth asserting lives in ``test_assembly_card`` and ``test_mission``,
where it runs without a display.

These tests skip cleanly on a headless machine.
"""

from __future__ import annotations

import pytest

from aerosizer import FlightMode, input_fields
from aerosizer.mission import PAYLOAD_FIELD
from kiosk import FLIGHT_MODES, PAGES, KioskScreen


@pytest.fixture
def screen(catalog):
    tkinter = pytest.importorskip("tkinter")
    try:
        instance = KioskScreen(catalog, fullscreen=False)
    except tkinter.TclError as error:
        pytest.skip(f"No display available: {error}")

    yield instance
    instance.destroy()


def _switch_to(screen, mode: FlightMode) -> None:
    while screen._mode is not mode:
        screen._mode_stepper._increase.invoke()
    screen.update()


def test_screen_builds_and_lays_out(screen):
    screen.update()

    assert screen.winfo_children()


@pytest.mark.parametrize("mode", list(FlightMode))
def test_the_inputs_are_whatever_the_mode_declared(screen, mode):
    """The kiosk never names a field. It renders what it is handed."""
    _switch_to(screen, mode)

    assert set(screen._field_steppers) == {field.key for field in input_fields(mode)}


def test_stepping_forward_visits_every_mode_and_wraps(screen):
    screen.update()

    visited = []
    for _ in range(len(FLIGHT_MODES) + 1):
        visited.append(screen._mode)
        screen._mode_stepper._increase.invoke()

    assert set(visited) == set(FLIGHT_MODES)
    assert visited[-1] is visited[0], "stepping past the last mode wraps to the first"


def test_stepping_backwards_wraps(screen):
    screen.update()
    first = screen._mode

    screen._mode_stepper._decrease.invoke()
    assert screen._mode is FLIGHT_MODES[-1]

    screen._mode_stepper._increase.invoke()
    assert screen._mode is first


def test_neither_mode_direction_is_ever_disabled(screen):
    # Modes wrap, so unlike the mission numbers there is no end to reach.
    for _ in range(len(FLIGHT_MODES) * 2):
        screen._mode_stepper._increase.invoke()
        screen.update()

        assert str(screen._mode_stepper._decrease.cget("state")) == "normal"
        assert str(screen._mode_stepper._increase.cget("state")) == "normal"


def test_the_panel_never_changes_size_as_modes_are_cycled(screen):
    """Modes ask for different numbers; the panel must not resize for them.

    Loiter needs two figures and the range modes one, so the input area is
    sized for the most demanding mode and holds that height throughout.
    """
    screen.update()

    panel_heights = set()
    for _ in FLIGHT_MODES:
        screen._mode_stepper._increase.invoke()
        screen.update()
        panel_heights.add(screen.winfo_reqheight())

    assert len(panel_heights) == 1


def test_payload_carries_across_a_mode_change(screen):
    screen.update()

    for _ in range(3):
        screen._field_steppers[PAYLOAD_FIELD.key]._increase.invoke()
    carried = screen._values[PAYLOAD_FIELD.key]

    screen._mode_stepper._increase.invoke()
    screen.update()

    assert screen._values[PAYLOAD_FIELD.key] == pytest.approx(carried)


@pytest.mark.parametrize("mode", list(FlightMode))
def test_every_field_steps_both_ways(screen, mode):
    _switch_to(screen, mode)

    for field in input_fields(mode):
        stepper = screen._field_steppers[field.key]

        before = screen._values[field.key]
        stepper._increase.invoke()
        assert screen._values[field.key] > before

        stepper._decrease.invoke()
        assert screen._values[field.key] == pytest.approx(before)


@pytest.mark.parametrize("mode", list(FlightMode))
def test_every_field_stays_within_its_declared_bounds(screen, mode):
    _switch_to(screen, mode)

    for field in input_fields(mode):
        stepper = screen._field_steppers[field.key]

        for _ in range(300):
            stepper._increase.invoke()
        assert screen._values[field.key] == pytest.approx(field.maximum)
        assert str(stepper._increase.cget("state")) == "disabled"

        for _ in range(300):
            stepper._decrease.invoke()
        assert screen._values[field.key] == pytest.approx(field.minimum)
        assert str(stepper._decrease.cget("state")) == "disabled"


def test_card_panel_is_rebuilt_rather_than_accumulated(screen):
    screen.update()
    before = len(screen._card_frame.winfo_children())

    for _ in range(5):
        screen._field_steppers[PAYLOAD_FIELD.key]._increase.invoke()
    screen.update()

    assert len(screen._card_frame.winfo_children()) == before


def test_every_control_label_is_drawable_by_the_panel_font(screen):
    """Regression: a typographic minus sign (U+2212) was not in the font.

    Tk draws a missing glyph as a box containing its hex codepoint, so the
    decrement button appeared on screen as a box reading 2212. Restricting
    control labels to ASCII removes the whole class of failure, which matters
    on a Raspberry Pi image carrying far fewer fonts than a desktop.
    """
    screen.update()

    for stepper in [screen._mode_stepper, *screen._field_steppers.values()]:
        for button in (stepper._decrease, stepper._increase):
            label = button.cget("text")
            assert label.isascii(), f"control label {label!r} may not render on the panel font"


def test_all_inputs_share_one_control_shape(screen):
    screen.update()

    steppers = [screen._mode_stepper, *screen._field_steppers.values()]
    widths = {stepper._value_label.winfo_width() for stepper in steppers}

    assert len(widths) == 1, "every input should align as one column"


@pytest.mark.parametrize("page", PAGES)
def test_no_card_text_is_cut_off_by_the_panel_edge(screen, page):
    """Regression: speed limit reasons ran off the right of the screen.

    The detail column was a fixed eight characters wide, which fitted
    "from nose" and truncated "at takeoff mass". Measured against the font
    rather than the widget, because a widget given an explicit width reports
    that width whether or not its text fits inside it.
    """
    from tkinter import font as tk_font

    screen._select_page(page)
    screen.update()

    frame = screen._card_frame
    for label in frame.winfo_children():
        text = label.cget("text")
        if not text:
            continue

        natural_width = tk_font.Font(font=label.cget("font")).measure(text)
        assert natural_width <= label.winfo_width(), f"{text!r} is clipped by its column"
        assert label.winfo_x() + natural_width <= frame.winfo_width(), (
            f"{text!r} runs past the right edge of the panel"
        )
