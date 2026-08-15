"""Kiosk screen: the aircraft-mounted display.

A fullscreen Tkinter app sized for a 3.5 inch panel. It is deliberately dumb.
Its only jobs are layout and event plumbing:

    * ``Requirements`` is the single source of truth. Widgets read from it and
      write to it. Application state is never queried back out of a widget.
    * The card panel is rebuilt wholesale from ``AssemblyCard`` data on every
      change. Nothing here holds a reference to a value label and updates it
      in place -- widgets you must keep in sync are where this kind of code
      rots, and on a screen this size a full redraw is free.
    * Every judgement about units, wording and severity was already made in
      ``aerosizer.assembly_card``. This module decides colours and pixels.

Run it with::

    python kiosk.py                # windowed, at true panel size
    python kiosk.py --fullscreen   # on the aircraft
"""

from __future__ import annotations

import argparse
import tkinter as tk
from dataclasses import replace
from pathlib import Path

from aerosizer import CatalogError, FlightMode, Requirements, load_catalog, recommend
from aerosizer.assembly_card import AssemblyCard, BannerSeverity, build_assembly_card
from aerosizer.parts import Catalog
from aerosizer.units import format_duration, hours_to_seconds

SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320

# Modes are shown one at a time and cycled through, so the interface is the
# same size whether there are four of them or forty. Adding a mode to the
# enum needs no change here at all.
FLIGHT_MODES = tuple(FlightMode)

# Input bounds are hard-coded placeholders. At T4 they are replaced by
# envelope(mode, catalog), which reports what is actually achievable and makes
# duration and payload re-clamp against each other.
DURATION_STEP = 15 * 60.0
DURATION_LIMITS = (15 * 60.0, 4 * 3600.0)
PAYLOAD_STEP = 0.5
PAYLOAD_LIMITS = (0.0, 8.0)

BACKGROUND = "#0d1117"
PANEL = "#161b22"
CONTROL = "#21262d"
RULE = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
DISABLED = "#484f58"
ACCENT = "#1f6feb"

SEVERITY_COLOUR = {
    BannerSeverity.CRITICAL: "#f85149",
    BannerSeverity.CAUTION: "#d29922",
    BannerSeverity.INFORMATION: "#3fb950",
}

LABEL_FONT = ("Helvetica", 8)
VALUE_FONT = ("Helvetica", 11, "bold")
# Stepper glyphs are ASCII and oversized: the panel font has no typographic
# minus, and Tk draws a missing glyph as a box containing its hex codepoint.
STEPPER_FONT = ("Helvetica", 13, "bold")
PREDICTION_FONT = ("Helvetica", 10, "bold")
RATIONALE_FONT = ("Helvetica", 7)
BANNER_FONT = ("Helvetica", 8, "bold")


class Stepper:
    """A labelled value with a decrement and an increment either side of it.

    Every input on this screen is one of these, which is what keeps the panel
    a fixed size: a stepper shows one value at a time, so the interface does
    not grow when the range of possible values does.

    Holds no state. It is told what to display and whether each direction is
    still available, and a direction that is unavailable is shown as disabled
    rather than silently doing nothing -- a button that absorbs a press with
    no effect is indistinguishable from a broken one.
    """

    VALUE_WIDTH = 13

    def __init__(
        self,
        parent: tk.Misc,
        label: str,
        on_step,
        decrease_label: str = "-",
        increase_label: str = "+",
    ) -> None:
        row = tk.Frame(parent, background=BACKGROUND)
        row.pack(fill=tk.X, padx=6, pady=1)

        tk.Label(
            row,
            text=label,
            font=LABEL_FONT,
            foreground=MUTED,
            background=BACKGROUND,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        # An empty weighted column pushes the control group to the right edge,
        # where a thumb reaches it.
        row.columnconfigure(1, weight=1)

        self._decrease = self._make_button(row, decrease_label, lambda: on_step(-1))
        self._decrease.grid(row=0, column=2, padx=(0, 2))

        self._value = tk.StringVar()
        self._value_label = tk.Label(
            row,
            textvariable=self._value,
            font=VALUE_FONT,
            foreground=TEXT,
            background=BACKGROUND,
            width=self.VALUE_WIDTH,
            anchor="center",
        )
        self._value_label.grid(row=0, column=3)

        self._increase = self._make_button(row, increase_label, lambda: on_step(1))
        self._increase.grid(row=0, column=4, padx=(2, 0))

    def refresh(self, text: str, can_decrease: bool = True, can_increase: bool = True) -> None:
        self._value.set(text)
        self._decrease.configure(state=tk.NORMAL if can_decrease else tk.DISABLED)
        self._increase.configure(state=tk.NORMAL if can_increase else tk.DISABLED)

    @staticmethod
    def _make_button(parent: tk.Misc, text: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            font=STEPPER_FONT,
            width=3,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            background=CONTROL,
            foreground=TEXT,
            disabledforeground=DISABLED,
            activebackground=ACCENT,
            activeforeground=TEXT,
            command=command,
        )


class KioskScreen(tk.Tk):
    """The whole interface: mission controls above, assembly card below."""

    def __init__(self, catalog: Catalog, fullscreen: bool) -> None:
        super().__init__()
        self._catalog = catalog
        self._requirements = Requirements(
            mode=FlightMode.LOITER,
            duration=hours_to_seconds(1.0),
            payload_mass=4.0,
        )

        self.title("Aircraft Configuration Advisor")
        self.configure(background=BACKGROUND)
        self.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}")
        self.resizable(False, False)
        if fullscreen:
            self.attributes("-fullscreen", True)
            self.bind("<Escape>", lambda _event: self.destroy())

        self._build_mission_controls()
        self._build_card_area()
        self._refresh()

    # ---------------------------------------------------------------- layout

    def _build_mission_controls(self) -> None:
        self._mode_stepper = Stepper(
            self, "MODE", self._step_mode, decrease_label="<", increase_label=">"
        )
        self._duration_stepper = Stepper(self, "DURATION", self._step_duration)
        self._payload_stepper = Stepper(self, "PAYLOAD", self._step_payload)

    def _build_card_area(self) -> None:
        tk.Frame(self, background=RULE, height=1).pack(fill=tk.X, padx=6, pady=(4, 0))

        self._card_frame = tk.Frame(self, background=BACKGROUND)
        self._card_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        self._prediction_label = tk.Label(
            self,
            font=PREDICTION_FONT,
            foreground=TEXT,
            background=PANEL,
            pady=3,
        )
        self._prediction_label.pack(fill=tk.X, padx=6)

        # Two lines are reserved whether or not the rationale needs them, so
        # that a longer sentence cannot shift the banner below it.
        self._rationale_label = tk.Label(
            self,
            font=RATIONALE_FONT,
            foreground=MUTED,
            background=BACKGROUND,
            wraplength=SCREEN_WIDTH - 20,
            justify=tk.LEFT,
            anchor="nw",
            height=2,
        )
        self._rationale_label.pack(fill=tk.X, padx=8, pady=(2, 2))

        self._banner_label = tk.Label(
            self,
            font=BANNER_FONT,
            background=BACKGROUND,
            wraplength=SCREEN_WIDTH - 12,
            pady=4,
        )
        self._banner_label.pack(fill=tk.X, side=tk.BOTTOM)

    # ----------------------------------------------------------- interaction

    def _select_mode(self, mode: FlightMode) -> None:
        self._requirements = replace(self._requirements, mode=mode)
        self._refresh()

    def _step_mode(self, direction: int) -> None:
        """Cycle to the neighbouring mode, wrapping at either end."""
        position = FLIGHT_MODES.index(self._requirements.mode) + direction
        self._select_mode(FLIGHT_MODES[position % len(FLIGHT_MODES)])

    def _step_duration(self, direction: int) -> None:
        stepped = self._requirements.duration + direction * DURATION_STEP
        self._requirements = replace(
            self._requirements, duration=_clamp(stepped, DURATION_LIMITS)
        )
        self._refresh()

    def _step_payload(self, direction: int) -> None:
        stepped = self._requirements.payload_mass + direction * PAYLOAD_STEP
        self._requirements = replace(
            self._requirements, payload_mass=_clamp(stepped, PAYLOAD_LIMITS)
        )
        self._refresh()

    # --------------------------------------------------------------- redraw

    def _refresh(self) -> None:
        """Recompute from requirements and redraw everything that derives."""
        # Modes wrap, so neither direction is ever unavailable.
        self._mode_stepper.refresh(self._requirements.mode.value.replace("_", " ").upper())

        duration = self._requirements.duration
        self._duration_stepper.refresh(
            format_duration(duration),
            can_decrease=duration > DURATION_LIMITS[0],
            can_increase=duration < DURATION_LIMITS[1],
        )

        payload = self._requirements.payload_mass
        self._payload_stepper.refresh(
            f"{payload:.1f} kg",
            can_decrease=payload > PAYLOAD_LIMITS[0],
            can_increase=payload < PAYLOAD_LIMITS[1],
        )

        self._render_card(build_assembly_card(recommend(self._requirements, self._catalog)))

    def _render_card(self, card: AssemblyCard) -> None:
        for existing in self._card_frame.winfo_children():
            existing.destroy()

        for row, entry in enumerate(card.assembly):
            tk.Label(
                self._card_frame,
                text=entry.label.upper(),
                font=LABEL_FONT,
                foreground=MUTED,
                background=BACKGROUND,
                anchor="w",
            ).grid(row=row, column=0, sticky="w", pady=1)

            tk.Label(
                self._card_frame,
                text=entry.value,
                font=VALUE_FONT,
                foreground=TEXT,
                background=BACKGROUND,
                anchor="e",
            ).grid(row=row, column=1, sticky="e", pady=1)

            tk.Label(
                self._card_frame,
                text=entry.detail or "",
                font=LABEL_FONT,
                foreground=MUTED,
                background=BACKGROUND,
                width=8,
                anchor="w",
            ).grid(row=row, column=2, sticky="w", padx=(4, 0))

        self._card_frame.columnconfigure(1, weight=1)

        self._prediction_label.configure(text="   ".join(card.prediction))
        self._rationale_label.configure(text=card.rationale)
        self._banner_label.configure(
            text=card.banner.headline,
            foreground=SEVERITY_COLOUR[card.banner.severity],
        )


def _clamp(value: float, limits: tuple[float, float]) -> float:
    lower, upper = limits
    return min(max(value, lower), upper)


def main() -> int:
    parser = argparse.ArgumentParser(description="Aircraft-mounted kiosk screen.")
    parser.add_argument("--fullscreen", action="store_true", help="Fill the panel.")
    parser.add_argument(
        "--parts",
        type=Path,
        default=Path(__file__).parent / "parts",
        help="Directory holding the part catalogue.",
    )
    arguments = parser.parse_args()

    try:
        catalog = load_catalog(arguments.parts)
    except CatalogError as error:
        print(f"Could not load the part catalogue: {error}")
        return 1

    KioskScreen(catalog, fullscreen=arguments.fullscreen).mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
