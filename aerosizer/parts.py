"""The physical parts a pilot can bolt together.

These are the catalogue types: plain, frozen descriptions of hardware that
exists in a crate. They hold only what is measured off a real part. Anything
that can be derived from those measurements is exposed as a property, so that
a catalogue entry can never contradict itself by declaring, say, both a span
and an inconsistent aspect ratio.

All stations are measured in metres aft of the fuselage datum, which is the
nose tip. Positive is aft.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Wing:
    """One interchangeable wing module, as a matched left/right pair."""

    name: str
    airfoil: str
    reference_area: float
    span: float
    root_chord: float
    tip_chord: float
    max_lift_coefficient: float
    mass: float
    aerodynamic_centre_station: float

    @property
    def aspect_ratio(self) -> float:
        return self.span**2 / self.reference_area

    @property
    def taper_ratio(self) -> float:
        return self.tip_chord / self.root_chord

    @property
    def mean_aerodynamic_chord(self) -> float:
        """Standard trapezoidal-planform MAC."""
        taper = self.taper_ratio
        return (2.0 / 3.0) * self.root_chord * (1.0 + taper + taper**2) / (1.0 + taper)


@dataclass(frozen=True)
class Empennage:
    """One interchangeable tail module.

    ``nominal_aerodynamic_centre_station`` is where the tail sits with the boom
    fully retracted. Extending the boom moves it aft by the extension.
    """

    name: str
    horizontal_tail_area: float
    vertical_tail_area: float
    mass: float
    nominal_aerodynamic_centre_station: float

    def aerodynamic_centre_station(self, tail_extension: float) -> float:
        return self.nominal_aerodynamic_centre_station + tail_extension


@dataclass(frozen=True)
class TailBoom:
    """The extendable boom. Not a catalogue choice -- it is the trim mechanism.

    ``detent_spacing`` is the granularity a pilot can actually set in the
    field, and therefore the granularity every tail-extension instruction must
    be quantised to.
    """

    max_extension: float
    detent_spacing: float
    mass_per_metre: float

    def quantise(self, extension: float) -> float:
        """Snap a solved extension to the nearest detent the pilot can set."""
        clamped = min(max(extension, 0.0), self.max_extension)
        detents = round(clamped / self.detent_spacing)
        return detents * self.detent_spacing


@dataclass(frozen=True)
class Fuselage:
    """The constant fuselage. Every configuration shares this one."""

    name: str
    structure_mass: float
    structure_centre_of_mass_station: float
    payload_station: float
    fuel_tank_station: float
    max_fuel_mass: float
    tail_boom: TailBoom


@dataclass(frozen=True)
class Engine:
    name: str
    max_shaft_power: float
    best_specific_fuel_consumption: float
    propeller_efficiency: float
    mass: float
    station: float


@dataclass(frozen=True)
class Catalog:
    """Everything in the crate.

    The engine is currently a single fixed part rather than a fourth
    selectable module (plan section 10, question 1). It is held here rather
    than on the fuselage so that promoting it to a module later is a change of
    one field, not a change of shape.
    """

    fuselage: Fuselage
    engine: Engine
    wings: tuple[Wing, ...]
    empennages: tuple[Empennage, ...]
