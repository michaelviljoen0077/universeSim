"""Panda3D application shell.

Opens a 3D window with a PBR pipeline + lighting and a starfield, draws one shaded
sphere per body with a fading orbit trail, and steps the physics ``World`` every
frame. Supports an orbit camera, click-to-select with a HUD readout, right-drag to
spawn bodies, live mass editing, collisions (merge), and JSON save/load.

Bodies are tracked by their stable ``World`` id (not array index), so spawns,
deletions, and merges all reconcile cleanly against the scene graph.

Run headless (no window) for smoke-testing: ``UniverseApp(headless=True)``.
"""

from __future__ import annotations

import math
from collections import deque
from pathlib import Path
from typing import Dict, Optional

from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    AmbientLight,
    ClockObject,
    LColor,
    LineSegs,
    Material,
    NodePath,
    Plane,
    Point3,
    PointLight,
    Vec3,
    loadPrcFileData,
)

from universesim.physics import World, AU_PER_KM, EARTH_MASS_MSUN
from universesim.scenarios import solar_system, REGISTRY as SCENARIO_REGISTRY
from universesim import persistence
from . import assets
from .geometry import make_glow_sprite, make_skybox, make_starfield, make_uv_sphere
from .hud import Hud

_globalClock = ClockObject.get_global_clock()

_BODY_COLORS = {
    "Sun": (1.00, 0.85, 0.40),
    "Mercury": (0.60, 0.60, 0.60),
    "Venus": (0.90, 0.80, 0.50),
    "Earth": (0.25, 0.45, 0.95),
    "Mars": (0.85, 0.40, 0.20),
    "Jupiter": (0.80, 0.62, 0.42),
    "Saturn": (0.85, 0.75, 0.55),
    "Uranus": (0.55, 0.80, 0.85),
    "Neptune": (0.30, 0.45, 0.80),
}
_DEFAULT_COLOR = (0.60, 0.70, 0.90)

# Bodies with a visible atmosphere -> halo tint (RGB).
_ATMOSPHERE = {
    "Earth": (0.35, 0.55, 1.00),
    "Venus": (0.95, 0.85, 0.55),
    "Jupiter": (0.85, 0.75, 0.60),
    "Saturn": (0.90, 0.82, 0.65),
    "Uranus": (0.65, 0.90, 0.95),
    "Neptune": (0.45, 0.60, 0.95),
}

# A spawned body's defaults (FR-INT-01).
_SPAWN_MASS = EARTH_MASS_MSUN          # ~1 Earth mass
_SPAWN_RADIUS = 6371.0 * AU_PER_KM     # ~Earth radius
_SPAWN_VEL_GAIN = 0.012                # AU/day of velocity per AU of drag

_SAVE_PATH = Path("universesim_save.json")


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _display_radius(physical_radius_au: float, is_star: bool) -> float:
    """Map a true physical radius (AU) to a visible render radius (log-compressed)."""
    r_km = max(physical_radius_au / AU_PER_KM, 1.0)
    base = 0.03 + 0.02 * math.log10(r_km)
    return base * (2.5 if is_star else 1.0)


class UniverseApp(ShowBase):
    """The interactive sandbox window."""

    def __init__(self, world: Optional[World] = None, headless: bool = False) -> None:
        if headless:
            loadPrcFileData("", "window-type none")
        loadPrcFileData("", "window-title UniverseSim")
        super().__init__()

        # In headless mode ``win`` may be absent entirely (not just None).
        self.has_window = getattr(self, "win", None) is not None

        self.world = world if world is not None else solar_system()
        self.sim_speed = 40.0
        self.paused = False
        self._substeps = 8

        # Body bookkeeping keyed by stable id.
        self.node_by_id: Dict[int, NodePath] = {}
        self.trail_by_id: Dict[int, deque] = {}
        self.color_by_id: Dict[int, tuple] = {}
        self.disp_by_id: Dict[int, float] = {}
        self._id_index: Dict[int, int] = {}   # id -> current array index, refreshed per frame
        self.trail_max = 600

        self.star_id = self._initial_star_id()
        self.selected_id: Optional[int] = None
        self.follow_id: Optional[int] = None   # body the camera is locked onto
        self.ui = None
        self._scenario_factory = solar_system  # for the Reset button

        # Orbit camera.
        self.cam_target = Vec3(0, 0, 0)
        self.cam_heading = 35.0
        self.cam_pitch = 28.0
        self.cam_distance = self._fit_distance()
        self._rotating = False
        self._left_moved = False
        self._last_mouse: Optional[tuple] = None
        self._spawn_origin: Optional[Vec3] = None

        self.show_trails = True
        self.trail_root: Optional[NodePath] = None
        self._trail_geom: Optional[NodePath] = None
        self.hud: Optional[Hud] = None
        self.selection_marker: Optional[NodePath] = None

        if self.has_window:
            import simplepbr
            self.pbr_pipeline = simplepbr.init()
            self.disable_mouse()
            self.setBackgroundColor(0.01, 0.01, 0.02)
            self._setup_sky()
            self.trail_root = self.render.attach_new_node("trails")
            self.trail_root.set_transparency(True)
            self.hud = Hud(self)
            self._setup_lights()
            self._setup_selection_marker()
            self._setup_input()
            from .ui import GameUI
            self.ui = GameUI(self)

        self._refresh_id_index()
        self._reconcile_bodies()
        self.taskMgr.add(self._update, "universesim-update")

    # -- identity helpers ---------------------------------------------------
    def _initial_star_id(self) -> int:
        if self.world.count == 0:
            return -1
        return self.world.ids[int(self.world.mass.argmax())]

    def _refresh_id_index(self) -> None:
        self._id_index = {bid: i for i, bid in enumerate(self.world.ids)}

    # -- scene construction / reconciliation --------------------------------
    def _fit_distance(self) -> float:
        if self.world.count == 0:
            return 3.0
        extent = float(max((Vec3(*p).length() for p in self.world.position), default=1.0))
        return _clamp(1.4 * extent, 2.0, 500.0)

    def _reconcile_bodies(self) -> None:
        """Make the scene graph + bookkeeping match the World's current bodies.

        Adds nodes for new ids, drops nodes for vanished ids (deleted/merged), and
        rescales survivors whose radius changed. Cheap no-op when nothing changed.
        """
        current = set(self.world.ids)

        for bid in list(self.node_by_id):
            if bid not in current:
                self.node_by_id.pop(bid).remove_node()
                self.trail_by_id.pop(bid, None)
                self.color_by_id.pop(bid, None)
                self.disp_by_id.pop(bid, None)

        for idx, bid in enumerate(self.world.ids):
            is_star = (bid == self.star_id)
            disp_r = _display_radius(float(self.world.radius[idx]) or 1e-5, is_star)
            self.disp_by_id[bid] = disp_r
            if bid not in self.node_by_id:
                name = self.world.names[idx]
                color = _BODY_COLORS.get(name, _DEFAULT_COLOR)
                self.color_by_id[bid] = color
                node = self._create_body_node(name, color, disp_r, is_star)
                node.reparent_to(self.render)
                node.set_pos(Vec3(*self.world.position[idx]))
                self.node_by_id[bid] = node
                self.trail_by_id[bid] = deque(maxlen=self.trail_max)
            else:
                self.node_by_id[bid].set_scale(disp_r)  # radius may have grown via merge

    def _create_body_node(self, name: str, color: tuple, disp_r: float,
                          is_star: bool) -> NodePath:
        """Build a body's sphere with texture (if available), and star/atmosphere FX."""
        node = make_uv_sphere(radius=disp_r, name=name)
        node.set_material(self._make_material(color, emissive=is_star), 1)

        texture_path = assets.texture_for_body(name) if self.has_window else None
        if texture_path:
            try:
                tex = self.loader.load_texture(texture_path)
            except OSError:
                tex = None  # missing/corrupt texture -> keep the flat colour
            if tex is not None:
                node.set_texture(tex, 1)
                node.clear_color()  # let the texture supply the colour

        if is_star:
            # Render the star unlit and full-bright so its surface texture glows,
            # then add an additive halo sprite for radiance.
            node.set_light_off()
            node.set_shader_off(1)
            if self.has_window:
                make_glow_sprite(color=color, size=disp_r * 7.0).reparent_to(node)
        elif self.has_window and name in _ATMOSPHERE:
            self._add_atmosphere(node, disp_r, _ATMOSPHERE[name])

        return node

    def _add_atmosphere(self, parent: NodePath, disp_r: float, tint: tuple) -> None:
        shell = make_uv_sphere(radius=disp_r * 1.08, lat_segments=16, lon_segments=24,
                               name="atmosphere")
        shell.set_two_sided(True)
        shell.set_light_off()
        shell.set_shader_off(1)
        shell.set_depth_write(False)
        shell.set_transparency(True)
        shell.set_color(tint[0], tint[1], tint[2], 0.25)
        shell.reparent_to(parent)

    def _make_material(self, color: tuple, emissive: bool) -> Material:
        r, g, b = color
        mat = Material()
        mat.set_base_color(LColor(r, g, b, 1.0))
        if emissive:
            mat.set_emission(LColor(r, g, b, 1.0))
            mat.set_roughness(1.0)
        else:
            mat.set_roughness(0.7)
            mat.set_metallic(0.0)
        return mat

    def _setup_sky(self) -> None:
        """Milky Way skybox if the texture is present, else a procedural starfield."""
        sky_tex = assets.named_texture("stars_milky_way")
        if sky_tex:
            make_skybox(sky_tex).reparent_to(self.render)
        else:
            make_starfield().reparent_to(self.render)

    def _setup_lights(self) -> None:
        plight = PointLight("starlight")
        plight.set_color(LColor(1.0, 0.96, 0.88, 1.0))
        self.star_light = self.render.attach_new_node(plight)
        self.render.set_light(self.star_light)

        ambient = AmbientLight("ambient")
        ambient.set_color(LColor(0.03, 0.03, 0.04, 1.0))
        self.render.set_light(self.render.attach_new_node(ambient))

    def _setup_selection_marker(self) -> None:
        marker = make_uv_sphere(radius=1.0, lat_segments=16, lon_segments=24, name="selection")
        marker.set_render_mode_wireframe()
        marker.set_light_off()
        marker.set_shader_off(1)
        marker.set_color(1.0, 0.95, 0.2, 1.0)
        marker.reparent_to(self.render)
        marker.hide()
        self.selection_marker = marker

    # -- input --------------------------------------------------------------
    def _setup_input(self) -> None:
        self.accept("mouse1", self._on_left_down)
        self.accept("mouse1-up", self._on_left_up)
        self.accept("mouse3", self._on_right_down)
        self.accept("mouse3-up", self._on_right_up)
        self.accept("wheel_up", self._zoom, [1 / 1.1])
        self.accept("wheel_down", self._zoom, [1.1])
        self.accept("space", self._toggle_pause)
        self.accept("t", self._toggle_trails)
        self.accept("delete", self._delete_selected)
        self.accept("]", self._edit_mass, [2.0])
        self.accept("[", self._edit_mass, [0.5])
        self.accept("arrow_up", self._scale_speed, [2.0])
        self.accept("arrow_down", self._scale_speed, [0.5])
        self.accept("f5", self._save)
        self.accept("f9", self._load)
        self.accept("escape", self.user_exit)

    def _on_left_down(self) -> None:
        self._rotating = True
        self._left_moved = False
        self._last_mouse = None

    def _on_left_up(self) -> None:
        self._rotating = False
        self._last_mouse = None
        if not self._left_moved:
            self._select(self._pick_body())

    def _on_right_down(self) -> None:
        self._spawn_origin = self._plane_point()

    def _on_right_up(self) -> None:
        end = self._plane_point()
        if self._spawn_origin is not None and end is not None:
            self._spawn_body(self._spawn_origin, (end - self._spawn_origin) * _SPAWN_VEL_GAIN)
        self._spawn_origin = None

    def _zoom(self, factor: float) -> None:
        self.cam_distance = _clamp(self.cam_distance * factor, 0.2, 1000.0)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused

    def _toggle_trails(self) -> None:
        self.show_trails = not self.show_trails
        if not self.show_trails and self._trail_geom is not None:
            self._trail_geom.remove_node()
            self._trail_geom = None

    def _scale_speed(self, factor: float) -> None:
        self.sim_speed = _clamp(self.sim_speed * factor, 0.1, 100000.0)

    def _edit_mass(self, factor: float) -> None:
        """Live-edit the selected body's mass (FR-INT-04)."""
        if self.selected_id is None:
            return
        idx = self.world.index_of(self.selected_id)
        if idx < 0:
            return
        self.world.mass[idx] *= factor
        self.world._acc = None  # forces depend on mass

    # -- public API used by the UI -----------------------------------------
    def set_scenario(self, name: str) -> None:
        factory = SCENARIO_REGISTRY.get(name)
        if factory is None:
            return
        self._scenario_factory = factory
        self.follow_id = None
        self.load_world(factory())

    def reset_scenario(self) -> None:
        self.follow_id = None
        self.load_world(self._scenario_factory())

    def set_trails(self, on: bool) -> None:
        self.show_trails = bool(on)
        if not on and self._trail_geom is not None:
            self._trail_geom.remove_node()
            self._trail_geom = None

    def set_speed(self, value: float) -> None:
        self.sim_speed = _clamp(float(value), 0.1, 100000.0)

    def nudge_speed(self, factor: float) -> None:
        self._scale_speed(factor)

    def spawn_at_target(self) -> None:
        """Drop a new body into a circular orbit near the current view centre.

        A discoverable alternative to right-drag: places a body at a sensible radius
        from the star, moving at the local circular speed, then selects it.
        """
        from universesim.physics import G_AU_MSUN_DAY
        star_idx = self._id_index.get(self.star_id, -1)
        center = (self.world.position[star_idx].copy() if star_idx >= 0
                  else self.cam_target_array())
        star_mass = float(self.world.mass[star_idx]) if star_idx >= 0 else 1.0
        a = max(self.cam_distance * 0.4, 0.3)               # orbit radius from the star
        pos = [center[0] + a, center[1], center[2]]
        v = (G_AU_MSUN_DAY * star_mass / a) ** 0.5
        # Circular velocity, carried in the star's frame so the orbit is stable.
        star_vel = (self.world.velocity[star_idx] if star_idx >= 0 else [0.0, 0.0, 0.0])
        vel = [star_vel[0], star_vel[1] + v, star_vel[2]]
        self._spawn_body(Vec3(*pos), Vec3(*vel))

    def cam_target_array(self):
        return [self.cam_target.x, self.cam_target.y, self.cam_target.z]

    def apply_edits(self, name=None, mass_earths=None, radius_km=None) -> None:
        if self.selected_id is None:
            return
        idx = self.world.index_of(self.selected_id)
        if idx < 0:
            return
        if name:
            self.world.names[idx] = name
            node = self.node_by_id.get(self.selected_id)
            if node is not None:
                node.set_name(name)
        if mass_earths is not None:
            self.world.mass[idx] = max(1e-12, float(mass_earths)) * EARTH_MASS_MSUN
            self.world._acc = None
        if radius_km is not None:
            self.world.radius[idx] = max(1.0, float(radius_km)) * AU_PER_KM
            new_disp = _display_radius(float(self.world.radius[idx]),
                                       self.selected_id == self.star_id)
            self.disp_by_id[self.selected_id] = new_disp
            node = self.node_by_id.get(self.selected_id)
            if node is not None:
                node.set_scale(new_disp)

    def focus_selected(self) -> None:
        if self.selected_id is not None:
            self.follow_id = self.selected_id

    def clear_focus(self) -> None:
        self.follow_id = None

    def selected_summary(self):
        """(name, mass_earths, radius_km, speed_kms, dist_au) for the UI, or None."""
        if self.selected_id is None:
            return None
        idx = self.world.index_of(self.selected_id)
        if idx < 0:
            return None
        import numpy as np
        from universesim.physics import KMS_PER_AU_DAY, KM_PER_AU
        name = self.world.names[idx]
        mass_e = float(self.world.mass[idx]) / EARTH_MASS_MSUN
        radius_km = float(self.world.radius[idx]) * KM_PER_AU
        speed = float(np.linalg.norm(self.world.velocity[idx])) * KMS_PER_AU_DAY
        star_idx = self._id_index.get(self.star_id, -1)
        dist = (float(np.linalg.norm(self.world.position[idx] - self.world.position[star_idx]))
                if star_idx >= 0 and idx != star_idx else 0.0)
        return name, mass_e, radius_km, speed, dist

    # -- picking & spawning -------------------------------------------------
    def _world_ray(self):
        if not self.has_window or not self.mouseWatcherNode.has_mouse():
            return None
        m = self.mouseWatcherNode.get_mouse()
        near, far = Point3(), Point3()
        self.camLens.extrude(m, near, far)
        near = self.render.get_relative_point(self.cam, near)
        far = self.render.get_relative_point(self.cam, far)
        return Vec3(near), Vec3(far - near)

    def _plane_point(self) -> Optional[Vec3]:
        ray = self._world_ray()
        if ray is None:
            return None
        origin, direction = ray
        plane = Plane(Vec3(0, 0, 1), Point3(0, 0, 0))
        hit = Point3()
        if plane.intersects_line(hit, Point3(origin), Point3(origin + direction)):
            return Vec3(hit)
        return None

    def _pick_body(self) -> Optional[int]:
        """Stable id of the nearest body the cursor ray pierces, else None."""
        ray = self._world_ray()
        if ray is None:
            return None
        origin, direction = ray
        d = direction.normalized()
        best_id, best_t = None, float("inf")
        for bid, node in self.node_by_id.items():
            center = node.get_pos(self.render)
            t = (center - origin).dot(d)
            if t < 0:
                continue
            if (center - (origin + d * t)).length() <= self.disp_by_id[bid] * 1.6 and t < best_t:
                best_id, best_t = bid, t
        return best_id

    def _spawn_body(self, position: Vec3, velocity: Vec3) -> None:
        self.world.add_body(
            mass=_SPAWN_MASS,
            position=[position.x, position.y, position.z],
            velocity=[velocity.x, velocity.y, velocity.z],
            radius=_SPAWN_RADIUS,
            name=f"Body {self.world._next_id + 1}",
        )
        new_id = self.world.ids[-1]
        self._refresh_id_index()
        self._reconcile_bodies()
        self._select(new_id)

    def _select(self, body_id: Optional[int]) -> None:
        self.selected_id = body_id
        if self.selection_marker is None:
            return
        if body_id is None:
            self.selection_marker.hide()
        else:
            self.selection_marker.show()

    def _delete_selected(self) -> None:
        if self.selected_id is None or self.selected_id == self.star_id:
            return  # the star is the light source; don't delete it
        idx = self.world.index_of(self.selected_id)
        if idx < 0:
            return
        self.world.remove_body(idx)
        self._refresh_id_index()
        self._reconcile_bodies()
        self._select(None)

    # -- save / load --------------------------------------------------------
    def _save(self) -> None:
        persistence.save_world(self.world, _SAVE_PATH)
        print(f"[universesim] saved scene -> {_SAVE_PATH}")

    def _load(self) -> None:
        if not _SAVE_PATH.exists():
            print(f"[universesim] no save file at {_SAVE_PATH}")
            return
        self.load_world(persistence.load_world(_SAVE_PATH))
        print(f"[universesim] loaded scene <- {_SAVE_PATH}")

    def load_world(self, world: World) -> None:
        """Replace the active world and rebuild the scene from scratch."""
        for node in list(self.node_by_id.values()):
            node.remove_node()
        self.node_by_id.clear()
        self.trail_by_id.clear()
        self.color_by_id.clear()
        self.disp_by_id.clear()
        self.world = world
        self.star_id = self._initial_star_id()
        self._select(None)
        self.cam_distance = self._fit_distance()
        self._refresh_id_index()
        self._reconcile_bodies()

    # -- per-frame update ---------------------------------------------------
    def _update(self, task):
        if not self.paused and self.world.count:
            sim_dt = _globalClock.get_dt() * self.sim_speed
            step = sim_dt / self._substeps
            for _ in range(self._substeps):
                self.world.step(step)
            events = self.world.resolve_collisions()
            self._refresh_id_index()
            if events:
                self._handle_merges(events)
            self._record_trails()

        self._sync_positions()
        if self.has_window:
            self._update_star_light()
            self._update_selection_marker()
            if self.show_trails:
                self._rebuild_trails()
            self._update_camera()
            if self.hud is not None:
                self.hud.update_status(self.world, self.sim_speed, self.paused)
            if self.ui is not None:
                self.ui.update()
        return task.cont

    def _handle_merges(self, events) -> None:
        # Follow selection onto the survivor if the selected body was absorbed.
        absorbed = {a: s for s, a in events}
        if self.selected_id in absorbed:
            self.selected_id = absorbed[self.selected_id]
        self._reconcile_bodies()

    def _sync_positions(self) -> None:
        for bid, node in self.node_by_id.items():
            node.set_pos(Vec3(*self.world.position[self._id_index[bid]]))

    def _update_star_light(self) -> None:
        idx = self._id_index.get(self.star_id, -1)
        if idx >= 0:
            self.star_light.set_pos(Vec3(*self.world.position[idx]))

    def _update_selection_marker(self) -> None:
        if self.selection_marker is None or self.selected_id is None:
            return
        idx = self._id_index.get(self.selected_id, -1)
        if idx < 0:
            self.selection_marker.hide()
            return
        self.selection_marker.show()
        self.selection_marker.set_pos(Vec3(*self.world.position[idx]))
        self.selection_marker.set_scale(self.disp_by_id[self.selected_id] * 1.4)

    def _record_trails(self) -> None:
        for bid, dq in self.trail_by_id.items():
            dq.append(tuple(self.world.position[self._id_index[bid]]))

    def _rebuild_trails(self) -> None:
        if self.trail_root is None:
            return
        if self._trail_geom is not None:
            self._trail_geom.remove_node()
            self._trail_geom = None

        segs = LineSegs()
        for bid, dq in self.trail_by_id.items():
            if bid == self.star_id or len(dq) < 2:
                continue
            r, g, b = self.color_by_id[bid]
            pts = list(dq)
            n = len(pts)
            segs.set_color(r, g, b, 0.0)
            segs.move_to(*pts[0])
            for k, p in enumerate(pts[1:], start=1):
                segs.set_color(r, g, b, k / (n - 1))
                segs.draw_to(*p)

        self._trail_geom = self.trail_root.attach_new_node(segs.create())
        self._trail_geom.set_light_off()
        self._trail_geom.set_shader_off(1)

    def _update_camera(self) -> None:
        # Lock the camera centre onto a followed body (click-to-focus).
        if self.follow_id is not None:
            idx = self._id_index.get(self.follow_id, -1)
            if idx >= 0:
                self.cam_target = Vec3(*self.world.position[idx])
            else:
                self.follow_id = None
                self.cam_target = Vec3(0, 0, 0)

        if self.mouseWatcherNode.has_mouse():
            mx = self.mouseWatcherNode.get_mouse_x()
            my = self.mouseWatcherNode.get_mouse_y()
            if self._rotating and self._last_mouse is not None:
                dx = mx - self._last_mouse[0]
                dy = my - self._last_mouse[1]
                if abs(dx) > 1e-4 or abs(dy) > 1e-4:
                    self._left_moved = True
                self.cam_heading -= dx * 180.0
                self.cam_pitch = _clamp(self.cam_pitch + dy * 180.0, -85.0, 85.0)
            self._last_mouse = (mx, my)

        h = math.radians(self.cam_heading)
        p = math.radians(self.cam_pitch)
        offset = Vec3(
            self.cam_distance * math.cos(p) * math.sin(h),
            -self.cam_distance * math.cos(p) * math.cos(h),
            self.cam_distance * math.sin(p),
        )
        self.camera.set_pos(self.cam_target + offset)
        self.camera.look_at(self.cam_target)
