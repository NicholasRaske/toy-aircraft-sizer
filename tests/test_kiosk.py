"""Smoke tests for the kiosk screen.

The widget layer is deliberately thin, so it is deliberately barely tested.
What matters is that it builds, that it survives every interaction, and that
it holds no state of its own -- everything else worth asserting lives in
``test_assembly_card`` where it can be checked without a display.

These tests skip cleanly on a headless machine.
"""

from __future__ import annotations

import pytest

from aerosizer import FlightMode
from kiosk import DURATION_LIMITS, FLIGHT_MODES, PAYLOAD_LIMITS, KioskScreen


@pytest.fixture
def screen(catalog):
    tkinter = pytest.importorskip("tkinter")
    try:
        instance = KioskScreen(catalog, fullscreen=False)
    except tkinter.TclError as error:
        pytest.skip(f"No display available: {error}")

    yield instance
    instance.destroy()


def test_screen_builds_and_lays_out(screen):
    screen.update()

    assert screen.winfo_children()


def test_every_mode_can_be_selected(screen):
    for mode in FlightMode:
        screen._select_mode(mode)
        screen.update()

        assert screen._requirements.mode is mode


def test_duration_stays_within_its_limits(screen):
    for _ in range(50):
        screen._step_duration(1)
    assert screen._requirements.duration == pytest.approx(DURATION_LIMITS[1])

    for _ in range(50):
        screen._step_duration(-1)
    assert screen._requirements.duration == pytest.approx(DURATION_LIMITS[0])


def test_payload_stays_within_its_limits(screen):
    for _ in range(50):
        screen._step_payload(1)
    assert screen._requirements.payload_mass == pytest.approx(PAYLOAD_LIMITS[1])

    for _ in range(50):
        screen._step_payload(-1)
    assert screen._requirements.payload_mass == pytest.approx(PAYLOAD_LIMITS[0])


def test_card_panel_is_rebuilt_rather_than_accumulated(screen):
    screen.update()
    before = len(screen._card_frame.winfo_children())

    for _ in range(5):
        screen._step_payload(1)
    screen.update()

    assert len(screen._card_frame.winfo_children()) == before


@pytest.mark.parametrize("stepper_name", ["_duration_stepper", "_payload_stepper"])
def test_stepper_buttons_are_wired_to_their_directions(screen, stepper_name):
    """Regression: exercise the buttons, not just the handlers behind them.

    The first version of this suite called the step handlers directly. It
    passed while the minus button sat unreachable at the far end of its row,
    so decrementing was impossible on the actual screen.
    """
    screen.update()
    stepper = getattr(screen, stepper_name)

    before = _mission_values(screen)
    stepper._decrease.invoke()
    assert _mission_values(screen) < before

    stepper._increase.invoke()
    assert _mission_values(screen) == pytest.approx(before)


def test_a_direction_at_its_limit_is_shown_as_disabled(screen):
    for _ in range(50):
        screen._step_payload(-1)
    screen.update()

    # Silent clamping is indistinguishable from a dead button.
    assert str(screen._payload_stepper._decrease.cget("state")) == "disabled"
    assert str(screen._payload_stepper._increase.cget("state")) == "normal"


def test_both_directions_are_available_away_from_the_limits(screen):
    screen.update()

    for stepper in (screen._duration_stepper, screen._payload_stepper):
        assert str(stepper._decrease.cget("state")) == "normal"
        assert str(stepper._increase.cget("state")) == "normal"


def _mission_values(screen) -> float:
    return screen._requirements.duration + screen._requirements.payload_mass


def test_every_button_label_is_drawable_by_the_panel_font(screen):
    """Regression: a typographic minus sign (U+2212) was not in the font.

    Tk draws a missing glyph as a box containing its hex codepoint, so the
    decrement button appeared on screen as a box reading 2212. Restricting
    control labels to ASCII removes the whole class of failure, which matters
    on a Raspberry Pi image carrying far fewer fonts than a desktop.
    """
    screen.update()

    for stepper in _steppers(screen):
        for button in (stepper._decrease, stepper._increase):
            label = button.cget("text")
            assert label.isascii(), f"control label {label!r} may not render on the panel font"


def test_stepping_forward_visits_every_mode_and_wraps(screen):
    screen.update()

    visited = []
    for _ in range(len(FLIGHT_MODES) + 1):
        visited.append(screen._requirements.mode)
        screen._mode_stepper._increase.invoke()

    assert set(visited) == set(FLIGHT_MODES)
    assert visited[-1] is visited[0], "stepping past the last mode wraps to the first"


def test_stepping_backwards_wraps(screen):
    screen.update()
    first = screen._requirements.mode

    screen._mode_stepper._decrease.invoke()
    assert screen._requirements.mode is FLIGHT_MODES[-1]

    screen._mode_stepper._increase.invoke()
    assert screen._requirements.mode is first


def test_neither_mode_direction_is_ever_disabled(screen):
    # Modes wrap, so unlike duration and payload there is no end to reach.
    for _ in range(len(FLIGHT_MODES) * 2):
        screen._mode_stepper._increase.invoke()
        screen.update()

        assert str(screen._mode_stepper._decrease.cget("state")) == "normal"
        assert str(screen._mode_stepper._increase.cget("state")) == "normal"


def test_the_panel_never_changes_size_as_modes_are_cycled(screen):
    """The property this control exists for.

    Showing one mode at a time is what makes the interface immune to the
    number of modes: the value is a fixed-width field, so no mode name can
    widen the row and no new entry in FlightMode can force a redesign.
    """
    screen.update()

    value_widths = set()
    panel_heights = set()
    for _ in FLIGHT_MODES:
        screen._mode_stepper._increase.invoke()
        screen.update()
        value_widths.add(screen._mode_stepper._value_label.winfo_width())
        panel_heights.add(screen.winfo_reqheight())

    assert len(value_widths) == 1, "the mode field must not resize to fit its content"
    assert len(panel_heights) == 1


def test_all_three_inputs_share_one_control_shape(screen):
    screen.update()

    widths = {stepper._value_label.winfo_width() for stepper in _steppers(screen)}
    assert len(widths) == 1, "mode, duration and payload should align as one column"


def _steppers(screen):
    return (screen._mode_stepper, screen._duration_stepper, screen._payload_stepper)


def _mission_values(screen) -> float:
    return screen._requirements.duration + screen._requirements.payload_mass
