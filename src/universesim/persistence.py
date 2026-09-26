"""Scenario save/load (FR-SCN-01).

Serializes a :class:`~universesim.physics.World` to a small, human-readable JSON
document and reconstructs it. The format matches REQUIREMENTS §9 (units are AU /
Msun / day). It captures the full dynamical state — names, masses, radii, positions,
velocities, and elapsed time — so a reload reproduces the scene exactly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from .physics import G_AU_MSUN_DAY, World

SCHEMA_VERSION = 1


def world_to_dict(world: World) -> dict:
    return {
        "version": SCHEMA_VERSION,
        "units": {"length": "AU", "mass": "Msun", "time": "day"},
        "time": world.time,
        "g": world.g,
        "softening": world.softening,
        "bodies": [
            {
                "name": world.names[i],
                "mass": float(world.mass[i]),
                "radius": float(world.radius[i]),
                "position": world.position[i].tolist(),
                "velocity": world.velocity[i].tolist(),
            }
            for i in range(world.count)
        ],
    }


def world_from_dict(data: dict) -> World:
    version = data.get("version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported scenario version: {version!r}")

    world = World(g=float(data.get("g", G_AU_MSUN_DAY)),
                  softening=float(data.get("softening", 0.0)))
    for body in data["bodies"]:
        world.add_body(
            mass=body["mass"],
            position=body["position"],
            velocity=body["velocity"],
            radius=body.get("radius", 0.0),
            name=body.get("name", ""),
        )
    world.time = float(data.get("time", 0.0))
    return world


def save_world(world: World, path: Union[str, Path]) -> Path:
    path = Path(path)
    path.write_text(json.dumps(world_to_dict(world), indent=2), encoding="utf-8")
    return path


def load_world(path: Union[str, Path]) -> World:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return world_from_dict(data)
