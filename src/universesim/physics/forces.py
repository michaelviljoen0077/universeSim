"""Gravitational force computation (FR-PHY-01).

Phase 0/1 uses a direct, fully vectorized O(N^2) pairwise solver. It is exact (no
tree approximation) and comfortably handles the MVP target of ~100 bodies. The
Barnes-Hut / GPU acceleration paths (NFR-SCALE-01) slot in here later behind the
same ``accelerations`` signature.
"""

from __future__ import annotations

import numpy as np


def accelerations(
    positions: np.ndarray,
    masses: np.ndarray,
    g: float,
    softening: float = 0.0,
) -> np.ndarray:
    """Newtonian gravitational acceleration on each body.

    Parameters
    ----------
    positions : (N, 3) float array of positions.
    masses    : (N,)   float array of masses.
    g         : gravitational constant in the active unit system.
    softening : Plummer softening length. Prevents the singular 1/r^2 blow-up when
        two bodies get arbitrarily close (numerical safety, also smooths collisions).

    Returns
    -------
    (N, 3) array of accelerations: a_i = G * sum_{j != i} m_j (x_j - x_i) / |x_j - x_i|^3
    """
    n = positions.shape[0]
    acc = np.zeros_like(positions)
    if n < 2:
        return acc

    # r[i, j] = x_j - x_i   -> shape (N, N, 3)
    r = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]

    # Squared distances with Plummer softening; diagonal -> inf so self-term drops out.
    dist2 = np.sum(r * r, axis=2) + softening * softening
    np.fill_diagonal(dist2, np.inf)

    inv_dist3 = dist2 ** -1.5            # 1 / |r|^3, shape (N, N)
    factor = g * masses[np.newaxis, :] * inv_dist3   # (N, N)

    # a_i = sum_j factor[i, j] * r[i, j]
    acc = np.einsum("ij,ijk->ik", factor, r)
    return acc


def potential_energy(
    positions: np.ndarray,
    masses: np.ndarray,
    g: float,
    softening: float = 0.0,
) -> float:
    """Total gravitational potential energy of the system.

    U = -G * sum_{i < j} m_i m_j / |x_i - x_j|   (softened consistently with the force).
    """
    n = positions.shape[0]
    if n < 2:
        return 0.0

    r = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    dist = np.sqrt(np.sum(r * r, axis=2) + softening * softening)
    np.fill_diagonal(dist, np.inf)   # self-pairs -> 1/inf == 0 (no divide-by-zero)
    inv_dist = 1.0 / dist

    mm = masses[:, np.newaxis] * masses[np.newaxis, :]
    # Sum over i<j == half the full symmetric sum.
    return -0.5 * g * float(np.sum(mm * inv_dist))
