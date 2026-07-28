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
