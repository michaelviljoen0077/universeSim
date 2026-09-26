"""In-app graphical interface (DirectGUI).

Replaces hidden hotkeys with a real interface: a bottom playback bar, a top-left
scenario menu + tools, and a right-hand inspector for editing the selected body.
Keyboard shortcuts still work; this just makes everything discoverable.

Built only when there is a window; all callbacks delegate to ``UniverseApp``.
"""

from __future__ import annotations

from direct.gui.DirectGui import (
    DGG,
    DirectButton,
    DirectCheckButton,
    DirectEntry,
    DirectFrame,
    DirectLabel,
    DirectOptionMenu,
)
from panda3d.core import TextNode

from universesim.scenarios import REGISTRY

# Palette.
_PANEL = (0.07, 0.08, 0.12, 0.86)
_BTN = (0.18, 0.21, 0.30, 1.0)
_BTN_HI = (0.28, 0.33, 0.45, 1.0)
_TXT = (0.90, 0.93, 1.00, 1.0)
_ACCENT = (0.35, 0.62, 1.0, 1.0)
_CLEAR = (0, 0, 0, 0)


class GameUI:
    def __init__(self, app) -> None:
        self.app = app
        self.typing = False        # a text field has focus -> app hotkeys are muted
        self._shown_id = object()  # sentinel forces an initial populate
        self._build_bottom_bar()
        self._build_top_bar()
        self._build_inspector()
        self.update()

    # -- widget helpers -----------------------------------------------------
    def _button(self, parent, text, pos, command, scale=0.05, width=None):
        kw = dict(parent=parent, text=text, scale=scale, pos=pos, command=command,
                  frameColor=_BTN, text_fg=_TXT, relief=DGG.FLAT,
                  text_scale=0.85, pad=(0.35, 0.3),
                  text_align=TextNode.ACenter)
        if width is not None:
            kw["frameSize"] = (-width, width, -0.6, 1.0)
        btn = DirectButton(**kw)
        btn.bind(DGG.WITHIN, lambda _e, b=btn: b.__setitem__("frameColor", _BTN_HI))
        btn.bind(DGG.WITHOUT, lambda _e, b=btn: b.__setitem__("frameColor", _BTN))
        return btn

    def _label(self, parent, text, pos, scale=0.045, align=TextNode.ALeft, fg=_TXT):
        return DirectLabel(parent=parent, text=text, scale=scale, pos=pos,
                           text_fg=fg, frameColor=_CLEAR, text_align=align)

    def _entry(self, parent, pos, width=9, command=None):
        return DirectEntry(parent=parent, scale=0.045, pos=pos, width=width,
                           frameColor=(0.02, 0.02, 0.04, 1.0), text_fg=_TXT,
                           initialText="", numLines=1,
                           focusInCommand=self._set_typing, focusInExtraArgs=[True],
                           focusOutCommand=self._set_typing, focusOutExtraArgs=[False],
                           command=command or (lambda _t=None: None))

    def _set_typing(self, value: bool) -> None:
        self.typing = value

    # -- bottom playback bar ------------------------------------------------
    def _build_bottom_bar(self) -> None:
        bar = DirectFrame(parent=self.app.a2dBottomCenter, frameColor=_PANEL,
                          frameSize=(-1.15, 1.15, 0.0, 0.13), pos=(0, 0, 0.02))
        self.bottom = bar
        self.pause_btn = self._button(bar, "Pause", (-0.85, 0, 0.065),
                                      self._toggle_pause, width=2.2)
        self._button(bar, "<<", (-0.5, 0, 0.065), lambda: self.app.nudge_speed(0.5), width=1.0)
        self.speed_lbl = self._label(bar, "", (-0.38, 0, 0.05), align=TextNode.ALeft)
        self._button(bar, ">>", (-0.04, 0, 0.065), lambda: self.app.nudge_speed(2.0), width=1.0)
        self.trails_chk = DirectCheckButton(
            parent=bar, text="Trails", scale=0.045, pos=(0.35, 0, 0.05),
            command=self._set_trails, indicatorValue=1, text_fg=_TXT,
            frameColor=_BTN, boxPlacement="left", relief=DGG.FLAT)
        self._button(bar, "Reset", (0.9, 0, 0.065), self.app.reset_scenario, width=2.0)

    # -- top-left scenario + tools -----------------------------------------
    def _build_top_bar(self) -> None:
        panel = DirectFrame(parent=self.app.a2dTopLeft, frameColor=_PANEL,
                            frameSize=(0.0, 0.62, -0.46, 0.0), pos=(0.03, 0, -0.03))
        self._label(panel, "UNIVERSE SIM", (0.05, 0, -0.06), scale=0.05, fg=_ACCENT)
        self._label(panel, "Scenario", (0.05, 0, -0.13))
        items = list(REGISTRY)
        current = self.app.scenario_name
        self.scenario_menu = DirectOptionMenu(
            parent=panel, scale=0.05, pos=(0.05, 0, -0.21),
            items=items, initialitem=items.index(current) if current in items else 0,
            command=self.app.set_scenario,
            frameColor=_BTN, text_fg=_TXT, highlightColor=_BTN_HI,
            relief=DGG.FLAT, text_scale=0.9, popupMarkerBorder=(0, 0))
        self._button(panel, "+ Add Body", (0.2, 0, -0.31), self.app.spawn_at_target, width=3.2)
        self._button(panel, "Save", (0.13, 0, -0.41), self.app._save, width=1.7)
        self._button(panel, "Load", (0.42, 0, -0.41), self.app._load, width=1.7)

    # -- right-hand inspector ----------------------------------------------
    def _build_inspector(self) -> None:
        panel = DirectFrame(parent=self.app.a2dRightCenter, frameColor=_PANEL,
                            frameSize=(-0.66, 0.0, -0.52, 0.52), pos=(-0.02, 0, 0))
        self.inspector = panel
        self.insp_title = self._label(panel, "No selection", (-0.62, 0, 0.45),
                                      scale=0.05, fg=_ACCENT)

        self._label(panel, "Name", (-0.62, 0, 0.34))
        # Pressing Enter in any field applies the edits, same as the Apply button.
        self.name_entry = self._entry(panel, (-0.62, 0, 0.27), command=self._apply)
        self._label(panel, "Mass (Earths)", (-0.62, 0, 0.16))
        self.mass_entry = self._entry(panel, (-0.62, 0, 0.09), command=self._apply)
        self._label(panel, "Radius (km)", (-0.62, 0, -0.02))
        self.radius_entry = self._entry(panel, (-0.62, 0, -0.09), command=self._apply)

        self._button(panel, "Apply", (-0.46, 0, -0.22), self._apply, width=2.4)
        self._button(panel, "Focus", (-0.18, 0, -0.22), self.app.focus_selected, width=2.4)
        self._button(panel, "Delete", (-0.32, 0, -0.33), self.app._delete_selected, width=2.4)
        self.insp_info = self._label(panel, "", (-0.62, 0, -0.45), scale=0.04,
                                     fg=(0.7, 0.8, 0.95, 1))
        self._fields = [self.name_entry, self.mass_entry, self.radius_entry]

    # -- callbacks ----------------------------------------------------------
    def _toggle_pause(self) -> None:
        self.app._toggle_pause()

    def _set_trails(self, value) -> None:
        self.app.set_trails(bool(value))

    def _apply(self, _text=None) -> None:
        name = self.name_entry.get().strip()
        mass = _to_float(self.mass_entry.get())
        radius = _to_float(self.radius_entry.get())
        self.app.apply_edits(name=name or None, mass_earths=mass, radius_km=radius)
        self._shown_id = object()  # repopulate so the fields show the clamped values

    # -- per-frame refresh --------------------------------------------------
    def update(self) -> None:
        self.pause_btn["text"] = "Play" if self.app.paused else "Pause"
        self.speed_lbl["text"] = f"{self.app.sim_speed:.0f} d/s"
        # Keep the checkbox in step with the "T" hotkey.
        if bool(self.trails_chk["indicatorValue"]) != self.app.show_trails:
            self.trails_chk["indicatorValue"] = int(self.app.show_trails)

        if self.app.selected_id != self._shown_id:
            self._shown_id = self.app.selected_id
            self._populate()

        summary = self.app.selected_summary()
        if summary is not None:
            _name, _m, _r, speed, dist = summary
            self.insp_info["text"] = (f"speed {speed:,.2f} km/s"
                                      + (f"   dist {dist:.3f} AU" if dist else ""))

    def _populate(self) -> None:
        summary = self.app.selected_summary()
        showing = summary is not None
        for field in self._fields:
            (field.show if showing else field.hide)()
        if not showing:
            self.insp_title["text"] = "No selection"
            self.insp_info["text"] = "Click a body to inspect it"
            return
        name, mass_e, radius_km, _speed, _dist = summary
        self.insp_title["text"] = name
        self.name_entry.enterText(name)
        self.mass_entry.enterText(f"{mass_e:.4g}")
        self.radius_entry.enterText(f"{radius_km:.0f}")


def _to_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None
