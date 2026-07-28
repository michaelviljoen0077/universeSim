"""Locate optional texture assets on disk.

Textures live in ``<project>/assets/textures/`` and are fetched by
``scripts/download_textures.py``. Everything here degrades gracefully: if a file is
missing, the lookup returns ``None`` and the renderer falls back to flat colours.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from panda3d.core import Filename

# .../src/universesim/render/assets.py -> project root is three parents up from src.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEXTURE_DIR = _PROJECT_ROOT / "assets" / "textures"

# Body name (as used in scenarios) -> texture file stem.
_BODY_TEXTURE = {
    "Sun": "sun",
    "Mercury": "mercury",
    "Venus": "venus",
    "Earth": "earth",
    "Moon": "moon",
    "Mars": "mars",
    "Jupiter": "jupiter",
    "Saturn": "saturn",
    "Uranus": "uranus",
    "Neptune": "neptune",
}


def _resolve(stem: str) -> Optional[str]:
    path = TEXTURE_DIR / f"{stem}.jpg"
    if not path.exists():
        return None
    # Panda3D wants its own '/c/...' path format, not a Windows 'C:\...' string.
    return Filename.from_os_specific(str(path)).get_fullpath()


def texture_for_body(name: str) -> Optional[str]:
    """Path to a body's surface texture, or None if unavailable."""
    stem = _BODY_TEXTURE.get(name)
    return _resolve(stem) if stem else None


def named_texture(stem: str) -> Optional[str]:
    """Path to a texture by file stem (e.g. 'stars_milky_way'), or None."""
    return _resolve(stem)


def any_textures_present() -> bool:
    return TEXTURE_DIR.exists() and any(TEXTURE_DIR.glob("*.jpg"))
