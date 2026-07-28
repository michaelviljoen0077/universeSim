# UniverseSim

A 3D, physics-based space sandbox inspired by *Universe Sandbox*. Spawn stars and
planets, watch real Newtonian gravity play out, and tinker with a living solar system.

See **[REQUIREMENTS.md](REQUIREMENTS.md)** for the full vision, scope, and roadmap.

> **Status:** Phase 1 MVP feature-complete. Engine-agnostic physics core (gravity,
> symplectic integrator, collisions) with a passing test suite, plus a Panda3D window
> with a starfield, PBR bodies, fading trails, an orbit camera, click-to-select, a HUD,
> right-drag spawning, live editing, and JSON save/load. Photoreal textures are the
> next step (the spheres are flat-shaded colours for now).

## Quick start

```powershell
# from the project root
py -3.9 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# download photoreal planet/star textures (CC BY 4.0, ~7 MB) — optional but recommended
.\.venv\Scripts\python.exe scripts\download_textures.py

# run the interactive window
.\.venv\Scripts\python.exe -m universesim --scenario sun-earth

# run the physics tests
.\.venv\Scripts\python.exe -m pytest
```

### Controls
| Input | Action |
|---|---|
| Left-drag | Orbit the camera |
| Left-click | Select a body (shows its info in the HUD) |
| Right-drag | Spawn a body — drag direction/length sets its velocity |
| Mouse wheel | Zoom in / out |
| Space | Pause / resume |
| `T` | Toggle orbit trails |
| `[` / `]` | Halve / double the selected body's mass |
| Delete | Remove the selected body (the star is protected) |
| Up / Down arrows | Speed up / slow down time |
| F5 / F9 | Save / load the scene (`universesim_save.json`) |
| Esc | Quit |

The HUD shows simulated time, body count, and time rate; selecting a body adds its
mass, speed, and distance to the star. Bodies that touch **merge**, conserving mass
and momentum.

### Scenarios
- `solar-system` — the Sun and eight planets, real masses/distances (default).
- `sun-earth` — Sun + Earth on a 1 AU circular orbit.
- `two-body` — a light planet orbiting a star; the simplest demo.

Run a specific one with `--scenario <name>`, e.g. `--scenario sun-earth`.

Headless smoke test (no window, for CI):
```powershell
.\.venv\Scripts\python.exe -m universesim --headless --frames 200
```

## Architecture

```
src/universesim/
  physics/        # engine-agnostic core (no rendering deps) — see REQUIREMENTS §8
    units.py      #   AU / Msun / day unit system + constants
    forces.py     #   vectorized O(N^2) gravity + potential energy
    world.py      #   SoA body store + stable ids + velocity-Verlet + collisions
  scenarios/      # preset systems (Phase 0/1: hand-built; later: JPL Horizons)
  persistence.py  # JSON scenario save/load
  render/         # Panda3D layer
    geometry.py   #   procedural UV sphere + starfield
    hud.py        #   on-screen status + selected-body readout
    app.py        #   window, orbit camera, PBR materials, picking, spawn, sim loop
  main.py         # CLI entry point
tests/            # physics + app tests (orbits, conservation, collisions, save/load)
```

**Key invariant:** `universesim.physics` never imports a renderer, so the simulation
runs and is tested headlessly.

## Tech
Python 3.9 · NumPy · Panda3D + `panda3d-simplepbr` (PBR rendering) · pytest.
(Targeting an upgrade to Python 3.12 once all wheels are confirmed; Numba/Barnes–Hut
acceleration arrives in a later phase — see REQUIREMENTS §7.)
