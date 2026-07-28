"""Preset systems the user can load.

Phase 0 ships hand-built toy presets. Phase 1 will replace ``sun_earth`` with a
full Solar System generated from JPL Horizons state vectors (REQUIREMENTS §12).
"""

from .presets import solar_system, sun_earth, two_body_demo

# Ordered registry of selectable presets: display name -> factory.
REGISTRY = {
    "Solar System": solar_system,
    "Sun + Earth": sun_earth,
    "Two-Body": two_body_demo,
}

# CLI-friendly slugs -> factory (kept for `--scenario`).
SLUGS = {
    "solar-system": solar_system,
    "sun-earth": sun_earth,
    "two-body": two_body_demo,
}

__all__ = ["solar_system", "sun_earth", "two_body_demo", "REGISTRY", "SLUGS"]
