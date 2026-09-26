"""Physics-core unit tests (REQUIREMENTS §11 Definition of Done).

These run headlessly with no rendering dependency. They pin down the two properties
that make orbits "look right" long-term: a known circular orbit closes on itself,
and the symplectic integrator conserves energy and momentum.
"""

import math

import numpy as np
import pytest

from universesim.physics import World, G_AU_MSUN_DAY
from universesim.scenarios import solar_system


def test_two_body_circular_orbit_closes():
    """A light body on a circular 1 AU orbit returns to its start after one period."""
    world = World()
    m_sun = 1.0
    m_planet = 1e-6  # ~ Earth mass; central body barely recoils
    a = 1.0          # orbit radius, AU

    # Circular speed for the two-body system about their common centre.
    v_circ = math.sqrt(G_AU_MSUN_DAY * (m_sun + m_planet) / a)

    world.add_body(mass=m_sun, position=[0, 0, 0], velocity=[0, 0, 0], name="Sun")
    world.add_body(mass=m_planet, position=[a, 0, 0], velocity=[0, v_circ, 0], name="Planet")

    period = 2.0 * math.pi * a / v_circ  # ~365.25 days
    start = world.position[1].copy()

    n_steps = 4000
    dt = period / n_steps
    for _ in range(n_steps):
        world.step(dt)

    drift = np.linalg.norm(world.position[1] - start)
    # Should return to within a milli-AU after a full revolution.
    assert drift < 1e-3, f"orbit did not close: drift={drift:.2e} AU"


def test_energy_conservation_stable_system():
    """Energy drifts only negligibly over a long run of a stable, bound system.

    We use a Sun with two well-separated planets on circular orbits — no close
    encounters — which is the regime the symplectic integrator is meant to handle
    (bounded orbits resolved by the time step). This is the property that makes a
    solar-system scene stay put for many simulated years (FR-PHY-02 / FR-PHY-06).
    """
    world = World()
    world.add_body(mass=1.0, position=[0, 0, 0], velocity=[0, 0, 0], name="Sun")
    for a, m in [(1.0, 1e-3), (2.5, 1e-3)]:
        v = math.sqrt(G_AU_MSUN_DAY * 1.0 / a)  # circular speed about the Sun
        world.add_body(mass=m, position=[a, 0, 0], velocity=[0, v, 0])

    e0 = world.total_energy()
    for _ in range(40000):  # ~110 simulated years at dt = 1 day
        world.step(1.0)
    e1 = world.total_energy()

    rel_drift = abs(e1 - e0) / abs(e0)
    assert rel_drift < 1e-4, f"energy not conserved: relative drift={rel_drift:.2e}"


def test_momentum_conservation():
    """Total linear momentum is conserved to ~machine precision."""
    world = World()
    world.add_body(mass=1.0, position=[0, 0, 0], velocity=[0, 0.005, 0])
    world.add_body(mass=0.5, position=[1, 0, 0], velocity=[0, -0.01, 0])
    world.add_body(mass=0.3, position=[-1, 0.5, 0], velocity=[0.002, 0, 0])

    p0 = world.momentum()
    for _ in range(5000):
        world.step(1.0)
    p1 = world.momentum()

    assert np.allclose(p0, p1, atol=1e-9), f"momentum changed: {p0} -> {p1}"


def test_add_and_remove_body():
    world = World()
    world.add_body(mass=1.0, position=[0, 0, 0], velocity=[0, 0, 0], name="A")
    idx = world.add_body(mass=2.0, position=[1, 0, 0], velocity=[0, 0, 0], name="B")
    assert world.count == 2
    assert world.names[idx] == "B"
    world.remove_body(0)
    assert world.count == 1
    assert world.names == ["B"]


def test_solar_system_is_centered_and_stable():
    """The Solar System preset starts in the COM frame and stays bound over years."""
    world = solar_system()
    assert world.count == 9  # Sun + 8 planets

    # COM frame: total momentum ~ zero at t=0.
    assert np.allclose(world.momentum(), [0, 0, 0], atol=1e-6)

    # Each planet should keep roughly its starting orbital radius after ~5 years
    # (circular orbits shouldn't wander far). Check Earth specifically.
    earth = world.names.index("Earth")
    r0 = np.linalg.norm(world.position[earth] - world.position[0])
    for _ in range(int(5 * 365)):  # ~5 years at dt = 1 day
        world.step(1.0)
    r1 = np.linalg.norm(world.position[earth] - world.position[0])
    assert abs(r1 - r0) / r0 < 0.05, f"Earth orbit radius drifted: {r0:.3f} -> {r1:.3f} AU"


def test_single_body_has_no_acceleration():
    world = World()
    world.add_body(mass=1.0, position=[0, 0, 0], velocity=[0.001, 0, 0])
    world.step(1.0)
    # Drifts in a straight line; no force on a lone body.
    assert np.allclose(world.position[0], [0.001, 0, 0])


def test_collision_merges_and_conserves():
    """Two overlapping bodies merge into one, conserving mass and momentum."""
    world = World()
    world.add_body(mass=2.0, position=[0, 0, 0], velocity=[0, 0.01, 0], radius=0.5, name="A")
    world.add_body(mass=1.0, position=[0.3, 0, 0], velocity=[0, -0.02, 0], radius=0.5, name="B")

    p_before = world.momentum().copy()
    m_before = float(world.mass.sum())

    events = world.resolve_collisions()

    assert len(events) == 1
    assert world.count == 1
    assert float(world.mass[0]) == pytest.approx(m_before)        # mass conserved
    assert np.allclose(world.momentum(), p_before, atol=1e-12)    # momentum conserved
    # Survivor keeps the more massive body's identity ("A").
    assert world.names[0] == "A"
    # Volume-additive radius: r' = (r1^3 + r2^3)^(1/3).
    assert float(world.radius[0]) == pytest.approx((0.5**3 + 0.5**3) ** (1 / 3))


def test_ids_are_stable_across_removal():
    world = World()
    world.add_body(mass=1.0, position=[0, 0, 0], velocity=[0, 0, 0], name="A")
    world.add_body(mass=1.0, position=[1, 0, 0], velocity=[0, 0, 0], name="B")
    world.add_body(mass=1.0, position=[2, 0, 0], velocity=[0, 0, 0], name="C")
    id_b, id_c = world.ids[1], world.ids[2]

    world.remove_body(0)  # remove A; B and C shift down in index but keep their ids

    assert world.index_of(id_b) == 0
    assert world.index_of(id_c) == 1
    assert world.names[world.index_of(id_c)] == "C"


def test_save_load_roundtrip(tmp_path):
    from universesim import persistence

    world = solar_system()
    for _ in range(50):
        world.step(1.0)

    path = persistence.save_world(world, tmp_path / "scene.json")
    restored = persistence.load_world(path)

    assert restored.count == world.count
    assert restored.names == world.names
    assert restored.time == pytest.approx(world.time)
    assert np.allclose(restored.position, world.position)
    assert np.allclose(restored.velocity, world.velocity)


def test_save_load_preserves_constants(tmp_path):
    from universesim import persistence

    world = World(g=1.0, softening=0.01)
    world.add_body(mass=1.0, position=[0, 0, 0], velocity=[0, 0, 0])
    restored = persistence.load_world(persistence.save_world(world, tmp_path / "s.json"))
    assert restored.g == pytest.approx(1.0)
    assert restored.softening == pytest.approx(0.01)
