"""The simulation ``World``: a Structure-of-Arrays body store plus the integrator.

Design notes (REQUIREMENTS §8):
- Body data lives in parallel NumPy arrays (SoA), not a list of objects, so the
  integrator stays vectorized and is trivial to hand to Numba/GPU later.
- The integrator is **velocity Verlet** (a symplectic leapfrog), chosen because it
  conserves energy well over long runs so orbits "look right" indefinitely without
  drifting or spiralling (decision Q1: looks-right > rigour; FR-PHY-02).
- Physics is engine-agnostic: nothing here imports a renderer.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

from . import forces
from .units import G_AU_MSUN_DAY


class World:
    """A gravitational N-body system in AU / Msun / day units."""

    def __init__(self, g: float = G_AU_MSUN_DAY, softening: float = 0.0) -> None:
        self.g = float(g)
        self.softening = float(softening)
        self.time: float = 0.0  # elapsed simulated time, in days

        # Structure-of-Arrays body store.
        self.position = np.zeros((0, 3), dtype=np.float64)
        self.velocity = np.zeros((0, 3), dtype=np.float64)
        self.mass = np.zeros((0,), dtype=np.float64)
        self.radius = np.zeros((0,), dtype=np.float64)
        self.names: List[str] = []

        # Stable per-body identity. Array indices shift when bodies are removed or
        # merged; ids never change, so the renderer can track a body across all that.
        self.ids: List[int] = []
        self._next_id = 0

        # Cached acceleration at the current position (velocity Verlet needs a(t)).
        self._acc: Optional[np.ndarray] = None

    # -- body management ----------------------------------------------------
    @property
    def count(self) -> int:
        return self.mass.shape[0]

    def add_body(
        self,
        mass: float,
        position,
        velocity,
        radius: float = 0.0,
        name: str = "",
    ) -> int:
        """Append a body and return its index. Invalidates the cached acceleration."""
        self.position = np.vstack([self.position, np.asarray(position, dtype=np.float64)])
        self.velocity = np.vstack([self.velocity, np.asarray(velocity, dtype=np.float64)])
        self.mass = np.append(self.mass, float(mass))
        self.radius = np.append(self.radius, float(radius))
        self.names.append(name or f"body{self.count}")
        self.ids.append(self._next_id)
        self._next_id += 1
        self._acc = None
        return self.count - 1

    def remove_body(self, index: int) -> None:
        self.position = np.delete(self.position, index, axis=0)
        self.velocity = np.delete(self.velocity, index, axis=0)
        self.mass = np.delete(self.mass, index)
        self.radius = np.delete(self.radius, index)
        del self.names[index]
        del self.ids[index]
        self._acc = None

    def index_of(self, body_id: int) -> int:
        """Current array index of a body by its stable id (-1 if it's gone)."""
        try:
            return self.ids.index(body_id)
        except ValueError:
            return -1

    # -- dynamics -----------------------------------------------------------
    def accelerations(self) -> np.ndarray:
        return forces.accelerations(self.position, self.mass, self.g, self.softening)

    def step(self, dt: float) -> None:
        """Advance the system by ``dt`` days using one velocity-Verlet step.

            v(t+dt/2) = v(t)      + a(t)    * dt/2
            x(t+dt)   = x(t)      + v(t+dt/2) * dt
            a(t+dt)   = f(x(t+dt))
            v(t+dt)   = v(t+dt/2) + a(t+dt) * dt/2
        """
        if self.count == 0:
            self.time += dt
            return

        if self._acc is None:
            self._acc = self.accelerations()

        half_dt = 0.5 * dt
        self.velocity += half_dt * self._acc          # kick (half)
        self.position += dt * self.velocity            # drift (full)
        new_acc = self.accelerations()
        self.velocity += half_dt * new_acc             # kick (half)
        self._acc = new_acc
        self.time += dt

    # -- collisions (FR-PHY-04) ---------------------------------------------
    def _find_overlapping_pair(self):
        """Indices (i, j) of the first pair whose spheres overlap, or None."""
        if self.count < 2:
            return None
        r = self.position[np.newaxis, :, :] - self.position[:, np.newaxis, :]
        dist = np.sqrt(np.sum(r * r, axis=2))
        rad_sum = self.radius[:, np.newaxis] + self.radius[np.newaxis, :]
        overlap = dist < rad_sum
        np.fill_diagonal(overlap, False)
        idx = np.argwhere(np.triu(overlap, k=1))
        if idx.size == 0:
            return None
        return int(idx[0, 0]), int(idx[0, 1])

    def resolve_collisions(self):
        """Merge every pair of overlapping bodies into one.

        A merge conserves total mass and linear momentum; the survivor sits at the
        centre of mass and grows by volume (r' = (r_i^3 + r_j^3)^(1/3)). The more
        massive body keeps its identity (so the star always survives as the star).

        Returns a list of ``(survivor_id, absorbed_id)`` events.
        """
        events = []
        while True:
            pair = self._find_overlapping_pair()
            if pair is None:
                break
            i, j = pair
            if self.mass[j] > self.mass[i]:  # survivor = more massive body
                i, j = j, i

            survivor_id, absorbed_id = self.ids[i], self.ids[j]
            mi, mj = self.mass[i], self.mass[j]
            total = mi + mj

            self.velocity[i] = (mi * self.velocity[i] + mj * self.velocity[j]) / total
            self.position[i] = (mi * self.position[i] + mj * self.position[j]) / total
            self.radius[i] = (self.radius[i] ** 3 + self.radius[j] ** 3) ** (1.0 / 3.0)
            self.mass[i] = total
            self.remove_body(j)

            events.append((survivor_id, absorbed_id))

        if events:
            self._acc = None
        return events

    # -- conserved-quantity diagnostics (FR-PHY-06) -------------------------
    def kinetic_energy(self) -> float:
        v2 = np.sum(self.velocity * self.velocity, axis=1)
        return 0.5 * float(np.sum(self.mass * v2))

    def potential_energy(self) -> float:
        return forces.potential_energy(self.position, self.mass, self.g, self.softening)

    def total_energy(self) -> float:
        return self.kinetic_energy() + self.potential_energy()

    def momentum(self) -> np.ndarray:
        """Total linear momentum vector (should be conserved to ~machine precision)."""
        return np.sum(self.mass[:, np.newaxis] * self.velocity, axis=0)

    def center_of_mass(self) -> np.ndarray:
        total = float(np.sum(self.mass))
        if total == 0.0:
            return np.zeros(3)
        return np.sum(self.mass[:, np.newaxis] * self.position, axis=0) / total
