"""On-screen HUD overlay (FR-CAM-08, FR-UI-02).

A thin wrapper around a few OnscreenText nodes: a status line (sim time, body count,
time rate), a selected-body readout, and a static controls hint. All values are
converted from internal AU/Msun/day units into human-friendly astronomical units.
"""

from __future__ import annotations

import numpy as np
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from universesim.physics import (
    DAYS_PER_YEAR,
    EARTH_MASS_MSUN,
    KMS_PER_AU_DAY,
)

class Hud:
    """Text overlay updated once per frame."""

    def __init__(self, base) -> None:
        # Top-right corner, clear of the on-screen panels (scenario menu top-left,
        # inspector right-centre, control bar bottom).
        self.status = OnscreenText(
            parent=base.a2dTopRight, align=TextNode.ARight,
            pos=(-0.04, -0.12), scale=0.05, fg=(1, 1, 1, 1),
            shadow=(0, 0, 0, 0.6), mayChange=True,
        )
        self.selected = OnscreenText(  # retained for API compatibility; unused by the UI
            parent=base.a2dBottomLeft, align=TextNode.ALeft,
            pos=(0.04, 0.18), scale=0.04, fg=(0.75, 0.88, 1.0, 1),
            shadow=(0, 0, 0, 0.6), mayChange=True,
        )

    def update_status(self, world, sim_speed: float, paused: bool) -> None:
        years = world.time / DAYS_PER_YEAR
        state = "PAUSED" if paused else f"{sim_speed:.0f} days/sec"
        self.status.setText(
            f"Time: {years:8.2f} yr\n"
            f"Bodies: {world.count}\n"
            f"Rate: {state}"
        )

    def update_selected(self, world, selected_id, star_id) -> None:
        """Show the selected body's info. ``selected_id`` is a stable id or None."""
        index = world.index_of(selected_id) if selected_id is not None else -1
        if index < 0:
            self.selected.setText("")
            return

        name = world.names[index]
        mass_earths = world.mass[index] / EARTH_MASS_MSUN
        speed_kms = float(np.linalg.norm(world.velocity[index])) * KMS_PER_AU_DAY

        lines = [f"[ {name} ]",
                 f"mass: {mass_earths:,.3g} Earth",
                 f"speed: {speed_kms:,.2f} km/s"]
        star_index = world.index_of(star_id) if star_id is not None else -1
        if star_index >= 0 and index != star_index:
            dist_au = float(np.linalg.norm(
                world.position[index] - world.position[star_index]))
            lines.append(f"dist to star: {dist_au:.3f} AU")
        self.selected.setText("\n".join(lines))
