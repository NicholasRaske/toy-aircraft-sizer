"""Mass and balance: what the aircraft weighs, and where it balances.

Every module contributes a mass at a station, and the assembly is their sum.
The itemised breakdown is exposed rather than only the totals, because the
centre of gravity is the number this tool most needs to get right, and anyone
checking it wants to see the moments that produced it.

Two things move the centre of gravity that a fixed parts list would miss:
extending the tail boom adds its own mass aft *and* carries the empennage
further aft, and burning fuel removes mass from wherever the tank sits.
"""

from __future__ import annotations

from dataclasses import dataclass

from aerosizer.config import Configuration, MassProperties

PAYLOAD = "Payload"
FUEL = "Fuel"


@dataclass(frozen=True)
class MassItem:
    """One contribution to the assembled mass, at its station aft of the nose."""

    name: str
    mass: float
    station: float

    @property
    def moment(self) -> float:
        return self.mass * self.station


def airframe_items(configuration: Configuration) -> tuple[MassItem, ...]:
    """Everything that is bolted on and stays there."""
    boom = configuration.fuselage.tail_boom
    extension = configuration.tail_extension

    return (
        MassItem(
            name=configuration.fuselage.name,
            mass=configuration.fuselage.structure_mass,
            station=configuration.fuselage.structure_centre_of_mass_station,
        ),
        MassItem(
            name=configuration.engine.name,
            mass=configuration.engine.mass,
            station=configuration.engine.station,
        ),
        MassItem(
            name=configuration.wing.name,
            mass=configuration.wing.mass,
            # The wing centroid sits slightly aft of its aerodynamic centre.
            # Treated as coincident until the structural model justifies more.
            station=configuration.wing.aerodynamic_centre_station,
        ),
        MassItem(
            name=configuration.empennage.name,
            mass=configuration.empennage.mass,
            station=configuration.empennage.aerodynamic_centre_station(extension),
        ),
        MassItem(
            name="Tail boom",
            mass=boom.mass_per_metre * extension,
            station=boom.root_station + extension / 2.0,
        ),
    )


def load_items(configuration: Configuration) -> tuple[MassItem, ...]:
    """What is put aboard for a given sortie."""
    return (
        MassItem(
            name=PAYLOAD,
            mass=configuration.payload_mass,
            station=configuration.fuselage.payload_station,
        ),
        MassItem(
            name=FUEL,
            mass=configuration.fuel_mass,
            station=configuration.fuselage.fuel_tank_station,
        ),
    )


def mass_items(configuration: Configuration) -> tuple[MassItem, ...]:
    return airframe_items(configuration) + load_items(configuration)


def mass_properties(configuration: Configuration) -> MassProperties:
    """Roll the assembly up into a total mass and a centre of gravity."""
    items = mass_items(configuration)
    all_up_mass = sum(item.mass for item in items)

    return MassProperties(
        all_up_mass=all_up_mass,
        empty_mass=sum(item.mass for item in airframe_items(configuration)),
        fuel_mass=configuration.fuel_mass,
        payload_mass=configuration.payload_mass,
        centre_of_gravity_station=centre_of_gravity(items),
    )


def centre_of_gravity(items: tuple[MassItem, ...]) -> float:
    """Mass-weighted mean station."""
    total_mass = sum(item.mass for item in items)
    if total_mass <= 0.0:
        raise ValueError("Cannot balance an assembly with no mass")
    return sum(item.moment for item in items) / total_mass
