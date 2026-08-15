"""The demonstration: the kiosk, and the aircraft it is describing, side by side.

    python demo.py

Two windows, one event loop. The kiosk is unchanged from the one that would
run on the aircraft; the aircraft view subscribes to it and redraws whenever
the recommendation changes.

This is a development tool and imports AeroSandbox, so it lives outside
``aerosizer`` like everything else that cannot ship. The kiosk itself remains
free of it -- run ``kiosk.py`` alone and you get exactly what flies.

Drawing an aircraft takes a second or two, which is far too slow to do on every
button press. Renders are cached by the parts they depend on, and with four
pairings in the catalogue the cache fills almost immediately.
"""

from __future__ import annotations

import argparse
import tkinter as tk
from pathlib import Path

import matplotlib

matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from aerosizer import CatalogError, Recommendation, load_catalog
from kiosk import BACKGROUND, MUTED, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT, KioskScreen
from tools.geometry import airplane_for_configuration

VIEW_WIDTH = 700
VIEW_HEIGHT = 560
WINDOW_GAP = 12

STATUS_FONT = ("Helvetica", 10, "bold")


class AircraftView(tk.Toplevel):
    """A window showing the aircraft the kiosk is currently recommending."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Aircraft")
        self.configure(background=BACKGROUND)
        self.geometry(f"{VIEW_WIDTH}x{VIEW_HEIGHT}")

        self._status = tk.Label(
            self,
            font=STATUS_FONT,
            foreground=TEXT,
            background=BACKGROUND,
            pady=6,
        )
        self._status.pack(fill=tk.X)

        self._plot_frame = tk.Frame(self, background=BACKGROUND)
        self._plot_frame.pack(fill=tk.BOTH, expand=True)

        self._detail = tk.Label(
            self,
            font=("Helvetica", 8),
            foreground=MUTED,
            background=BACKGROUND,
            pady=4,
        )
        self._detail.pack(fill=tk.X)

        self._drawings: dict[tuple, object] = {}
        self._canvas: FigureCanvasTkAgg | None = None
        self._showing: tuple | None = None

    def show(self, recommendation: Recommendation) -> None:
        configuration = recommendation.configuration
        signature = (
            configuration.wing.name,
            configuration.empennage.name,
            round(configuration.tail_extension, 3),
        )
        if signature == self._showing:
            return

        self._status.configure(
            text=f"{configuration.wing.name}  +  {configuration.empennage.name}"
        )
        results = recommendation.results
        self._detail.configure(
            text=(
                f"span {configuration.wing.span:.2f} m   "
                f"area {configuration.wing.reference_area:.2f} m2   "
                f"tail {configuration.tail_extension * 1000:.0f} mm   "
                f"all-up {results.mass.all_up_mass:.1f} kg   "
                f"L/D {results.lift_to_drag_max:.1f}   "
                f"static margin {results.balance.static_margin:.0%}"
            )
        )

        self._draw(signature, configuration)
        self._showing = signature

    def _draw(self, signature: tuple, configuration) -> None:
        figure = self._drawings.get(signature)
        if figure is None:
            figure = _isometric_figure(configuration)
            self._drawings[signature] = figure

        # Rebuilt wholesale rather than mutated, for the same reason the
        # assembly card is.
        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()

        self._canvas = FigureCanvasTkAgg(figure, master=self._plot_frame)
        self._canvas.draw()
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


def _isometric_figure(configuration):
    """Render one configuration and hand back the figure it drew into."""
    airplane = airplane_for_configuration(configuration)
    airplane.draw_wireframe(show=False)

    figure = plt.gcf()
    figure.patch.set_facecolor(BACKGROUND)
    for axes in figure.axes:
        axes.set_facecolor(BACKGROUND)

    # Each pyplot figure owns a hidden Tk window, and mainloop runs until the
    # process has none left, so a cached figure would outlive the demo.
    plt.close(figure)
    return figure


def main() -> int:
    parser = argparse.ArgumentParser(description="Kiosk and aircraft, side by side.")
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

    kiosk = KioskScreen(catalog, fullscreen=False)
    kiosk.geometry(f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}+40+80")

    view = AircraftView(kiosk)
    view.geometry(f"{VIEW_WIDTH}x{VIEW_HEIGHT}+{40 + SCREEN_WIDTH + WINDOW_GAP}+80")

    # Closing either window ends the demonstration.
    view.protocol("WM_DELETE_WINDOW", kiosk.destroy)

    kiosk.subscribe(view.show)
    kiosk.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
