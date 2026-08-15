"""The four objects the whole tool is built around.

``Requirements``     what the pilot asks for
``Configuration``    a fully determined aircraft, ready to evaluate
``Results``          what that aircraft will do
``Recommendation``   the configuration chosen for those requirements, and why

The important distinction is between ``Requirements`` and ``Configuration``.
A ``Configuration`` leaves nothing to be solved: the fuel is already decided,
the tail extension is already decided. That is what lets ``analyze`` be a pure
evaluation, with every iterative solve living in ``recommend``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aerosizer.parts import Empennage, Engine, Fuselage, Wing

SEA_LEVEL_ELEVATION = 0.0
STANDARD_TEMPERATURE = 288.15


class FlightMode(Enum):
    """What the pilot is optimising for. Chosen first; sets everything else."""

    LOITER = "loiter"
    RANGE = "range"
    SPEED = "speed"
    SHORT_FIELD = "short_field"


class Fidelity(Enum):
    """How much a number deserves to be trusted.

    Carried on every ``Results`` so that the tool can be honest about its own
    maturity. Until the real polars and the part-load fuel model land, the
    assembly card must say so in a way a pilot cannot miss.
    """

    PLACEHOLDER = "placeholder"
    PRELIMINARY = "preliminary"
    VALIDATED = "validated"


@dataclass(frozen=True)
class Requirements:
    """The mission, as stated by the pilot."""

    mode: FlightMode
    duration: float
    payload_mass: float
    field_elevation: float = SEA_LEVEL_ELEVATION
    field_temperature: float = STANDARD_TEMPERATURE


@dataclass(frozen=True)
class Configuration:
    """One assembled aircraft, with nothing left to solve."""

    fuselage: Fuselage
    engine: Engine
    wing: Wing
    empennage: Empennage
    tail_extension: float
    fuel_mass: float
    payload_mass: float

    @property
    def tail_arm(self) -> float:
        """Distance from the wing aerodynamic centre to the tail's."""
        return (
            self.empennage.aerodynamic_centre_station(self.tail_extension)
            - self.wing.aerodynamic_centre_station
        )


@dataclass(frozen=True)
class Results:
    """What a configuration will do.

    Every field is always populated. There is deliberately no ``Optional``
    here meaning "not computed yet" -- a half-filled result breeds None checks
    that never get cleaned up. Immature numbers are reported at low
    ``fidelity`` instead of being left absent.
    """

    fidelity: Fidelity

    all_up_mass: float
    centre_of_gravity_station: float

    stall_speed: float
    cruise_speed: float
    max_level_speed: float

    lift_to_drag_max: float
    endurance: float
    still_air_range: float
    rate_of_climb: float

    static_margin: float
    horizontal_tail_volume: float
    vertical_tail_volume: float


@dataclass(frozen=True)
class Candidate:
    """One evaluated configuration, with its score under the chosen mode."""

    configuration: Configuration
    results: Results
    figure_of_merit: float


@dataclass(frozen=True)
class Recommendation:
    """The answer: what to build, what it will do, and what it beat.

    ``considered`` holds every candidate that was evaluated, ranked best
    first. The chosen configuration is simply the head of that list. Keeping
    the whole ranking rather than just the winner is what lets an expert ask
    the question they always ask first -- what did this beat, and why were the
    others dropped?
    """

    requirements: Requirements
    considered: tuple[Candidate, ...]
    rationale: str

    @property
    def chosen(self) -> Candidate:
        return self.considered[0]

    @property
    def runner_up(self) -> Candidate | None:
        return self.considered[1] if len(self.considered) > 1 else None

    @property
    def configuration(self) -> Configuration:
        return self.chosen.configuration

    @property
    def results(self) -> Results:
        return self.chosen.results
