"""Headless tests for the app layer.

These construct ``UniverseApp`` with no window and exercise the non-rendering logic:
that spawning, deleting, merging, and loading keep the id-keyed bookkeeping in sync
with the World. Picking/camera/HUD need a display and aren't covered here.
"""

import pytest

from panda3d.core import Vec3

from universesim.render.app import UniverseApp
from universesim.scenarios import two_body_demo


@pytest.fixture
def app():
    a = UniverseApp(world=two_body_demo(), headless=True)
    yield a
    a.destroy()


def _assert_consistent(a):
    ids = set(a.world.ids)
    assert set(a.node_by_id) == ids
    assert set(a.trail_by_id) == ids
    assert set(a.disp_by_id) == ids
    assert set(a.color_by_id) == ids


def test_starts_consistent(app):
    assert app.world.count == 2
    _assert_consistent(app)


def test_spawn_keeps_consistency(app):
    before = app.world.count
    app._spawn_body(Vec3(2, 0, 0), Vec3(0, 0.01, 0))
    assert app.world.count == before + 1
    assert app.selected_id == app.world.ids[-1]  # newest body is selected
    _assert_consistent(app)


def test_delete_keeps_consistency(app):
    app._spawn_body(Vec3(2, 0, 0), Vec3(0, 0.01, 0))
    app._delete_selected()
    assert app.world.count == 2
    assert app.selected_id is None
    _assert_consistent(app)


def test_cannot_delete_star(app):
    app._select(app.star_id)
    app._delete_selected()
    assert app.world.count == 2
    _assert_consistent(app)


def test_edit_mass(app):
    bid = app.world.ids[1]
    app._select(bid)
    idx = app.world.index_of(bid)
    m0 = float(app.world.mass[idx])
    app._edit_mass(2.0)
    assert float(app.world.mass[app.world.index_of(bid)]) == pytest.approx(m0 * 2.0)


def test_step_runs_headless(app):
    for _ in range(10):
        app.taskMgr.step()
    assert app.world.time > 0.0
    _assert_consistent(app)


def test_hud_selected_handles_none_and_id(app):
    """Regression: HUD must accept a None selection (nothing selected) and a real id.

    Built without a window, so we bypass Hud.__init__ and stub the text node.
    """
    from universesim.render.hud import Hud

    class _Text:
        def setText(self, value):
            self.value = value

    hud = Hud.__new__(Hud)
    hud.selected = _Text()

    hud.update_selected(app.world, None, app.star_id)        # nothing selected
    assert hud.selected.value == ""

    bid = app.world.ids[1]
    hud.update_selected(app.world, bid, app.star_id)         # a real body
    assert app.world.names[1] in hud.selected.value


def test_existing_bodies_keep_size_after_spawn(app):
    """Regression: reconciling must not re-apply the display radius on top of itself.

    Body geometry is a unit sphere scaled to the display radius, so after a spawn
    (which reconciles every body) each node's scale must still equal its radius.
    """
    app._spawn_body(Vec3(2, 0, 0), Vec3(0, 0.01, 0))
    for bid, node in app.node_by_id.items():
        lo, hi = node.get_tight_bounds(app.render)
        rendered_radius = (hi.x - lo.x) / 2.0
        assert rendered_radius == pytest.approx(app.disp_by_id[bid], rel=1e-3)


def test_reset_uses_launched_scenario():
    from universesim.scenarios import sun_earth

    a = UniverseApp(world=sun_earth(), headless=True, scenario_factory=sun_earth)
    try:
        assert a.scenario_name == "Sun + Earth"
        a._spawn_body(Vec3(2, 0, 0), Vec3(0, 0.01, 0))
        a.reset_scenario()
        assert a.world.names == ["Sun", "Earth"]
        _assert_consistent(a)
    finally:
        a.destroy()


def test_load_world_clears_focus(app):
    app.follow_id = app.world.ids[1]
    app.load_world(two_body_demo())
    assert app.follow_id is None


def test_star_identity_follows_merge(app):
    """If a heavier body swallows the star, the survivor becomes the star."""
    star_idx = app.world.index_of(app.star_id)
    star_pos = app.world.position[star_idx]
    app._spawn_body(Vec3(*star_pos), Vec3(0, 0, 0))
    big = app.selected_id
    app.world.mass[app.world.index_of(big)] = 10.0
    app.follow_id = app.star_id

    events = app.world.resolve_collisions()
    app._refresh_id_index()
    app._handle_merges(events)

    assert app.star_id == big
    assert app.follow_id == big
    _assert_consistent(app)


def test_hotkeys_ignored_while_typing(app):
    class _UI:
        typing = True

    app._setup_input()
    app.ui = _UI()
    app._select(app.world.ids[1])
    app.messenger.send("delete")
    assert app.world.count == 2  # not deleted while typing

    app.ui.typing = False
    app.messenger.send("delete")
    assert app.world.count == 1
