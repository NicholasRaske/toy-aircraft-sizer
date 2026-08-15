"""The objects the whole tool is built around.

``Requirements``     what the pilot asks for
``Configuration``    a fully determined aircraft, ready to evaluate
``Results``          what that aircraft is capable of
``Recommendation``   the configuration chosen for those requirements, and why

The important distinction is between ``Requirements`` and ``Configuration``.
A ``Configuration`` leaves nothing to be solved: the fuel is already decided,
the tail extension is already decided. That is what lets ``analyze`` be a pure
evaluation, with every iterative solve living in ``recommend``.

The second distinction is between what an aircraft *is capable of* and what it
*does on a given sortie*. ``Results`` is the former -- how slowly it can fly,
how efficiently, where it balances. Mission outcomes such as fuel burned and
time elapsed belong to a flight log, and arrive with the mission model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aerosizer.atmosphere import SEA_LEVEL_ELEVATION, SEA_LEVEL_TEMPERATURE
from aerosizer.parts import Empennage, Engine, Fuselage, Wing


class FlightMode(Enum):
    """The shape of the sortie.

    A mode selects which mission profile is flown and which numbers the pilot
    is asked for. It does not select an objective: every mode is ranked the
    same way, on the fuel needed to complete the mission that was stated.
    """

    LOITER = "loiter"
    ONE_WAY_RANGE = "one_way_range"
    RETURN_RANGE = "return_range"


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
    field_temperature: float = SEA_LEVEL_TEMPERATURE


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
class Limited:
    """A value, together with whatever stopped it being better.

    Several speeds on this aircraft are set by something other than the
    textbook optimum. Minimum-power speed, for instance, falls below the stall
    speed at typical masses, so loiter is stall-limited rather than
    power-limited -- and reporting the unattainable optimum would mean
    promising an endurance the aircraft cannot fly.

    Carrying the reason lets the expert view explain itself, gives the
    tie-break rule a real margin to sort on, and gives each new constraint we
    discover somewhere to go other than another special case.

    ``margin`` is expressed in the same units as ``value``.
    """

    value: float
    limited_by: str
    margin: float


@dataclass(frozen=True)
class MassProperties:
    """Where the mass is, and therefore where the aircraft balances."""

    all_up_mass: float
    empty_mass: float
    fuel_mass: float
    payload_mass: float
    centre_of_gravity_station: float


@dataclass(frozen=True)
class SpeedEnvelope:
    """The speeds one configuration can fly, at one mass.

    Not a fixed property of the aircraft: stall speed goes as the square root
    of weight, so the envelope is narrowest at takeoff and widens as fuel
    burns.

    ``min_power_speed`` and ``min_drag_speed`` are the unclipped theoretical
    optima, kept for the expert view. The speeds actually flown are the
    ``Limited`` ones, which respect stall margin.
    """

    stall_speed: float
    min_power_speed: float
    min_drag_speed: float
    loiter_speed: Limited
    cruise_speed: Limited
    max_level_speed: Limited


@dataclass(frozen=True)
class Balance:
    """Longitudinal stability of the assembled aircraft."""

    neutral_point_station: float
    static_margin: float
    horizontal_tail_volume: float
    vertical_tail_volume: float


@dataclass(frozen=True)
class Results:
    """What a configuration is capable of.

    Every field is always populated. There is deliberately no ``Optional``
    here meaning "not computed yet" -- a half-filled result breeds None checks
    that never get cleaned up. Immature numbers are reported at low
    ``fidelity`` instead of being left absent.
    """

    fidelity: Fidelity
    mass: MassProperties
    envelope: SpeedEnvelope
    balance: Balance
    lift_to_drag_max: float


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
