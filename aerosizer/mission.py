"""What the pilot is actually asking the aircraft to do.

A mission is an ordered sequence of segments. Two kinds cover everything this
aircraft is asked to fly: cover a distance, or hold station for a time. A mode
is then just a template that builds a profile from two or three numbers the
pilot states.

    Loiter           Cruise(d) -> Loiter(t) -> Cruise(d)
    One-way range    Cruise(d)
    Return range     Cruise(d) -> Cruise(d)

Adding a survey pattern or a multi-leg sortie later is a new template, not new
physics -- the code that flies a profile never learns what mode it came from.

Modes also declare the numbers they need. An interface builds one control per
declared field and never branches on the mode, so a new mode costs no interface
changes at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class FlightMode(Enum):
    """The shape of the sortie.

    A mode selects which profile is flown and which numbers the pilot is asked
    for. It does not select an objective: every mode is ranked the same way, on
    the fuel needed to complete the mission that was stated.
    """

    LOITER = "loiter"
    ONE_WAY_RANGE = "one_way_range"
    RETURN_RANGE = "return_range"


class Quantity(Enum):
    """What kind of number a field holds, so the display edge can format it."""

    DISTANCE = "distance"
    DURATION = "duration"
    MASS = "mass"


@dataclass(frozen=True)
class CruiseSegment:
    """Cover a distance."""

    distance: float


@dataclass(frozen=True)
class LoiterSegment:
    """Hold station for a time."""

    duration: float


Segment = CruiseSegment | LoiterSegment


class Mission(Protocol):
    """Anything that can say which segments it is made of."""

    def profile(self) -> tuple[Segment, ...]: ...


@dataclass(frozen=True)
class LoiterMission:
    """Fly out, hold station, fly home."""

    transit_distance: float
    station_time: float

    def profile(self) -> tuple[Segment, ...]:
        transit = CruiseSegment(self.transit_distance)
        return (transit, LoiterSegment(self.station_time), transit)


@dataclass(frozen=True)
class OneWayRangeMission:
    """Fly there. Recovery elsewhere is somebody else's problem."""

    distance: float

    def profile(self) -> tuple[Segment, ...]:
        return (CruiseSegment(self.distance),)


@dataclass(frozen=True)
class ReturnRangeMission:
    """Fly there and back."""

    distance: float

    def profile(self) -> tuple[Segment, ...]:
        leg = CruiseSegment(self.distance)
        return (leg, leg)


@dataclass(frozen=True)
class InputField:
    """One number a mode needs, and the range it may take.

    ``key`` is the attribute name on the mission it builds, so an interface can
    read a value back out without knowing which mission it is holding.

    Bounds are hard-coded for now. They are replaced by the achievable
    frontier once the flyability gate exists, at which point they start
    depending on each other -- more payload will mean less range.
    """

    key: str
    label: str
    quantity: Quantity
    minimum: float
    maximum: float
    step: float
    default: float


PAYLOAD_FIELD = InputField(
    key="payload_mass",
    label="PAYLOAD",
    quantity=Quantity.MASS,
    minimum=0.0,
    maximum=8.0,
    step=0.5,
    default=4.0,
)

_KILOMETRE = 1000.0
_MINUTE = 60.0

MISSION_FIELDS: dict[FlightMode, tuple[InputField, ...]] = {
    FlightMode.LOITER: (
        InputField(
            key="transit_distance",
            label="TO SITE",
            quantity=Quantity.DISTANCE,
            minimum=0.0,
            maximum=60.0 * _KILOMETRE,
            step=1.0 * _KILOMETRE,
            default=10.0 * _KILOMETRE,
        ),
        InputField(
            key="station_time",
            label="ON STATION",
            quantity=Quantity.DURATION,
            minimum=5.0 * _MINUTE,
            maximum=240.0 * _MINUTE,
            step=5.0 * _MINUTE,
            default=60.0 * _MINUTE,
        ),
    ),
    FlightMode.ONE_WAY_RANGE: (
        InputField(
            key="distance",
            label="DISTANCE",
            quantity=Quantity.DISTANCE,
            minimum=1.0 * _KILOMETRE,
            maximum=400.0 * _KILOMETRE,
            step=5.0 * _KILOMETRE,
            default=60.0 * _KILOMETRE,
        ),
    ),
    FlightMode.RETURN_RANGE: (
        InputField(
            key="distance",
            label="DISTANCE",
            quantity=Quantity.DISTANCE,
            minimum=1.0 * _KILOMETRE,
            maximum=200.0 * _KILOMETRE,
            step=5.0 * _KILOMETRE,
            default=30.0 * _KILOMETRE,
        ),
    ),
}

_MISSION_TYPES: dict[FlightMode, type] = {
    FlightMode.LOITER: LoiterMission,
    FlightMode.ONE_WAY_RANGE: OneWayRangeMission,
    FlightMode.RETURN_RANGE: ReturnRangeMission,
}


def mission_fields(mode: FlightMode) -> tuple[InputField, ...]:
    """The numbers this mode needs, beyond the payload every mode carries."""
    return MISSION_FIELDS[mode]


def input_fields(mode: FlightMode) -> tuple[InputField, ...]:
    """Everything an interface must ask for, in the order it should ask."""
    return (*mission_fields(mode), PAYLOAD_FIELD)


def default_values(mode: FlightMode) -> dict[str, float]:
    return {field.key: field.default for field in input_fields(mode)}


def mission_from(mode: FlightMode, values: Mapping[str, float]) -> Mission:
    """Build the mission a mode describes, from the numbers it declared."""
    arguments = {field.key: values[field.key] for field in mission_fields(mode)}
    return _MISSION_TYPES[mode](**arguments)


def mode_of(mission: Mission) -> FlightMode:
    """Which mode produced this mission.

    Derived rather than stored, so a mission and its mode can never disagree.
    """
    for mode, mission_type in _MISSION_TYPES.items():
        if isinstance(mission, mission_type):
            return mode
    raise ValueError(f"No flight mode corresponds to {type(mission).__name__}")


def total_distance(profile: tuple[Segment, ...]) -> float:
    return sum(
        segment.distance for segment in profile if isinstance(segment, CruiseSegment)
    )


def total_loiter_time(profile: tuple[Segment, ...]) -> float:
    return sum(
        segment.duration for segment in profile if isinstance(segment, LoiterSegment)
    )
