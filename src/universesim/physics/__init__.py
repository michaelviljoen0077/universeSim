"""Engine-agnostic physics core.

Importing this package must never pull in Panda3D or any rendering dependency,
so the simulation can run and be unit-tested headlessly (NFR-MAINT-01).
"""

from .units import (
    G_AU_MSUN_DAY,
    AU_PER_KM,
    KM_PER_AU,
    MSUN_PER_KG,
    DAY_PER_S,
    DAYS_PER_YEAR,
    EARTH_MASS_MSUN,
    KMS_PER_AU_DAY,
)
from .world import World

__all__ = [
    "World",
    "G_AU_MSUN_DAY",
    "AU_PER_KM",
    "KM_PER_AU",
    "MSUN_PER_KG",
    "DAY_PER_S",
    "DAYS_PER_YEAR",
    "EARTH_MASS_MSUN",
    "KMS_PER_AU_DAY",
]
