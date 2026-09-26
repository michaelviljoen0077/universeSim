"""Hand-built starter scenarios (Phase 0).

Values are in the internal unit system (AU / Msun / day). Radii are physical (true
sizes); the renderer log-compresses them into a visible display size, so collisions
use real radii while everything stays see-able on screen.
"""

from __future__ import annotations

import math

import numpy as np

from universesim.physics import World, G_AU_MSUN_DAY, AU_PER_KM, EARTH_MASS_MSUN

_SUN_RADIUS_KM = 696_000.0
_EARTH_RADIUS_KM = 6_371.0


def two_body_demo() -> World:
    """A light planet on a clean circular orbit around a star. The simplest 'it works'."""
    world = World()
    a = 1.0
    m_star, m_planet = 1.0, 1e-6
    v = math.sqrt(G_AU_MSUN_DAY * (m_star + m_planet) / a)
    world.add_body(mass=m_star, position=[0, 0, 0], velocity=[0, 0, 0],
                   radius=_SUN_RADIUS_KM * AU_PER_KM, name="Star")
    world.add_body(mass=m_planet, position=[a, 0, 0], velocity=[0, v, 0],
                   radius=_EARTH_RADIUS_KM * AU_PER_KM, name="Planet")
    return world


def sun_earth() -> World:
    """Sun + Earth on a circular 1 AU orbit, in the centre-of-mass frame."""
    world = World()
    m_sun = 1.0
    m_earth = EARTH_MASS_MSUN
    a = 1.0
    v = math.sqrt(G_AU_MSUN_DAY * (m_sun + m_earth) / a)

    # Put the system in the COM frame so it doesn't drift across the screen.
    v_sun = -v * m_earth / m_sun
    world.add_body(mass=m_sun, position=[0, 0, 0], velocity=[0, v_sun, 0],
                   radius=_SUN_RADIUS_KM * AU_PER_KM, name="Sun")
    world.add_body(mass=m_earth, position=[a, 0, 0], velocity=[0, v, 0],
                   radius=_EARTH_RADIUS_KM * AU_PER_KM, name="Earth")
    return world


# Real Solar System data (J2000-era). Masses in Msun, semi-major axes in AU, mean
# physical radii in km. Orbits are approximated as circular and coplanar — fine for
# "looks right" (decision Q1); eccentricity/inclination arrive with the JPL Horizons
# importer in a later Phase 1 step (FR-SCN-02).
_SUN_MASS = 1.0

# name        mass (Msun)   semi-major axis (AU)   radius (km)
_PLANETS = [
    ("Mercury", 1.651e-7,   0.387,                 2_440.0),
    ("Venus",   2.447e-6,   0.723,                 6_052.0),
    ("Earth",   3.003e-6,   1.000,                 6_371.0),
    ("Mars",    3.213e-7,   1.524,                 3_390.0),
    ("Jupiter", 9.543e-4,   5.203,                69_911.0),
    ("Saturn",  2.857e-4,   9.537,                58_232.0),
    ("Uranus",  4.365e-5,  19.191,                25_362.0),
    ("Neptune", 5.149e-5,  30.070,                24_622.0),
]


def solar_system() -> World:
    """The Sun and eight planets on circular, coplanar orbits, in the COM frame."""
    world = World()
    world.add_body(
        mass=_SUN_MASS,
        position=[0, 0, 0],
        velocity=[0, 0, 0],
        radius=_SUN_RADIUS_KM * AU_PER_KM,
        name="Sun",
    )

    # Stagger starting angles so the planets don't begin in a straight line.
    for i, (name, mass, a, radius_km) in enumerate(_PLANETS):
        angle = 2.0 * math.pi * i / len(_PLANETS)
        v_circ = math.sqrt(G_AU_MSUN_DAY * (_SUN_MASS + mass) / a)
        pos = [a * math.cos(angle), a * math.sin(angle), 0.0]
        # Velocity perpendicular to the radius, in the orbital (prograde) direction.
        vel = [-v_circ * math.sin(angle), v_circ * math.cos(angle), 0.0]
        world.add_body(mass=mass, position=pos, velocity=vel,
                       radius=radius_km * AU_PER_KM, name=name)

    # Recoil the Sun so total momentum is zero — keeps the system centred on screen.
    planet_momentum = np.sum(
        world.mass[1:, np.newaxis] * world.velocity[1:], axis=0
    )
    world.velocity[0] = -planet_momentum / world.mass[0]
    return world
