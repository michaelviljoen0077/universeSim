# UniverseSim — Requirements Document

> A 3D, physics-based space sandbox inspired by *Universe Sandbox*.
> Status: **Draft v0.1** · Owner: Michael · Last updated: 2026-06-26

---

## 1. Vision

Build an interactive 3D simulator where the user creates, destroys, and tinkers
with astronomical bodies and watches real (if simplified) physics play out:
gravity, orbits, collisions, stellar evolution, and climate. There is no win
condition — the value is experimentation and "what if" play.

**North star:** feature parity with the fun core of *Universe Sandbox*.
**Reality check:** this is a long-term project. It is delivered in phases (§7);
each phase is independently usable and fun.

---

## 2. Goals & Non-Goals

### Goals
- Physically plausible N-body gravity in 3D, in real time, for hundreds of bodies.
- Direct manipulation: spawn, drag, fling, delete, and edit bodies live.
- Time control: pause, slow, fast-forward, reverse.
- Load real systems (Solar System, notable exoplanets) and save custom scenarios.
- Visually legible 3D: orbit camera, trails, scalable units, body labels.
- Run on a normal desktop (Windows first) at interactive frame rates.

### Non-Goals (at least initially)
- Scientific-grade accuracy suitable for research/publication.
- Multiplayer / networked simulation.
- VR (deferred; possible later).
- Full general relativity (use Newtonian gravity; GR effects optional/cosmetic).
- Mobile platforms.

---

## 3. Target Users
- Hobbyists / space enthusiasts who want to "play with planets."
- Students / educators demonstrating orbital mechanics and astrophysics intuitively.
- The developer (you) as a learning project in graphics + physics + simulation.

---

## 4. Tech Stack (Recommended)

| Concern | Choice | Why |
|---|---|---|
| Language | **Python 3.11+** | Fits your existing toolchain; fast iteration. |
| 3D engine | **Panda3D** | Full 3D engine in Python: scene graph, camera, picking, GUI, asset loading. |
| Physics math | **NumPy** (vectorized) | Fast array math for N-body without C++. |
| Hot loops | **Numba** (JIT) | Compiles the integrator/force kernels to near-native speed. |
| Scaling path | **CuPy / compute shaders** | GPU offload for large N (Phase 4+). |
| Spatial accel | **Barnes–Hut octree** | Reduces O(N²) gravity to O(N log N) for big scenes. |
| UI | Panda3D DirectGUI (MVP) → **Dear PyGui / imgui** if needed | Sliders, panels, body editor. |
| Save format | **JSON** (+ optional gzip) | Human-readable scenarios; easy versioning. |
| Tests | **pytest** | Physics unit tests (energy/momentum conservation, known orbits). |

**Fallback:** if pure-Python performance becomes the hard limit for the full-clone
ambitions, port the renderer/UI to **Godot 4** (GDScript/C#) and keep the physics
design from this doc. Decision checkpoint at end of Phase 2.

---

## 5. Functional Requirements

IDs are stable references. Priority: **P0** = MVP, **P1** = important, **P2** = later.

### 5.1 Physics & Simulation Core
- **FR-PHY-01 (P0)** Newtonian gravity between all bodies (pairwise or Barnes–Hut).
- **FR-PHY-02 (P0)** Numerical integrator with good energy behavior — use
  **velocity Verlet / leapfrog** (symplectic: orbits stay stable and "look right"
  long-term without drifting). RK4 is **optional/deferred**, only if a specific
  scenario needs higher short-term accuracy. *(Decision: "looks right" > rigor.)*
- **FR-PHY-03 (P0)** Adjustable, stable time step decoupled from frame rate
  (fixed-step physics, interpolated rendering).
- **FR-PHY-04 (P0)** Collision detection (sphere overlap) with at least
  **merge-on-collision** (conserve mass + momentum).
- **FR-PHY-05 (P1)** Collision **fragmentation/debris** (break-up on high-energy impact).
- **FR-PHY-06 (P1)** Conservation diagnostics surfaced to UI (total energy, momentum drift).
- **FR-PHY-07 (P2)** Stellar evolution: luminosity, radius, temperature change with
  age/mass; main-sequence → red giant → remnant; supernova event.
- **FR-PHY-08 (P2)** Climate/temperature model per body (insolation from stars,
  albedo, distance) driving surface temperature and ice/water state.
- **FR-PHY-09 (P2)** Roche limit / tidal disruption effects.
- **FR-PHY-10 (P2)** Relativistic precession as an optional cosmetic correction.

### 5.2 Bodies & Data Model
- **FR-BOD-01 (P0)** Body types: star, planet, moon, asteroid, black hole (gravity-only at first).
- **FR-BOD-02 (P0)** Each body has: mass, radius, position, velocity, name, color/material, type.
- **FR-BOD-03 (P1)** Composition/material affecting density, appearance, collision behavior.
- **FR-BOD-04 (P1)** Derived/displayed properties: orbital period, semi-major axis,
  eccentricity, surface gravity, escape velocity, temperature.
- **FR-BOD-05 (P2)** Rings, atmospheres (visual + physical influence).

### 5.3 Interaction & Editing
- **FR-INT-01 (P0)** Spawn a new body (click/drag to set position; drag velocity vector to set initial velocity).
- **FR-INT-02 (P0)** Select a body (click / pick).
- **FR-INT-03 (P0)** Delete selected body.
- **FR-INT-04 (P0)** Live-edit selected body's properties via a panel (mass, radius, velocity, name, color).
- **FR-INT-05 (P1)** Grab & drag a body during sim; fling to impart velocity.
- **FR-INT-06 (P1)** Duplicate body; "launch" tool to fire bodies into a system.
- **FR-INT-07 (P2)** Add body in a stable orbit around a target (auto-compute velocity).

### 5.4 Simulation Control
- **FR-SIM-01 (P0)** Play / pause.
- **FR-SIM-02 (P0)** Time-rate control (e.g., 1 sec = 1 hour … 1 year), scalable slider.
- **FR-SIM-03 (P1)** Reverse time (re-integrate backward) and step-by-step stepping.
- **FR-SIM-04 (P1)** Reset scenario to its initial state.

### 5.5 Camera & Rendering (3D) — *target: photorealistic*
- **FR-CAM-01 (P0)** Orbit camera: rotate, pan, zoom; smooth across huge scale range.
- **FR-CAM-02 (P0)** Focus/follow a selected body.
- **FR-CAM-03 (P0)** Render bodies as **PBR-shaded** 3D spheres (real albedo/roughness),
  not flat colors — photoreal is a primary goal, so PBR materials start at MVP.
- **FR-CAM-04 (P0)** **Textured planets** with day-map (+ normal/specular where available)
  from real imagery; promoted to P0 since the look depends on it.
- **FR-CAM-05 (P0)** Orbit **trails** (fading paths behind moving bodies).
- **FR-CAM-06 (P0)** HDR starfield skybox; physically-bright **emissive stars** with bloom.
- **FR-CAM-07 (P1)** Logarithmic/scaled rendering so tiny moons and vast orbits are both visible.
- **FR-CAM-08 (P1)** Body labels + on-screen HUD (sim time, body count, selected body info).
- **FR-CAM-09 (P1)** **Atmospheric scattering** (rim glow on planets with atmospheres),
  city-lights night map for Earth, ring rendering for gas giants.
- **FR-CAM-10 (P1)** Tone mapping + bloom post-processing pass for the photoreal look.
- **FR-CAM-11 (P2)** Visual collision effects (debris, flashes, supernova bloom),
  cloud layers, lens flare.

> **Rendering note:** photoreal in Panda3D relies on `simplepbr` (PBR pipeline) plus
> custom shaders for atmosphere/bloom — doable but manual. This is the strongest
> reason to evaluate the **Godot 4** fallback at the Phase 2 checkpoint, since Godot
> ships HDR/PBR/post-processing out of the box.

### 5.6 Scenarios, Presets & Persistence
- **FR-SCN-01 (P0)** Save current scene to a file; load it back exactly.
- **FR-SCN-02 (P0)** Built-in preset: the real **Solar System** (accurate masses/orbits).
- **FR-SCN-03 (P1)** More presets: binary star, Earth–Moon, asteroid belt, "throw a planet at Earth."
- **FR-SCN-04 (P1)** Scenario browser/menu with thumbnails or descriptions.
- **FR-SCN-05 (P2)** Import real-world bodies from a bundled catalog (planets, major moons, exoplanets).

### 5.7 UI / UX
- **FR-UI-01 (P0)** Toolbar for tools (spawn, select, delete) and play/pause/time.
- **FR-UI-02 (P0)** Property inspector panel for the selected body.
- **FR-UI-03 (P1)** Unit display with sensible astronomical units (AU, km, Earth masses, etc.).
- **FR-UI-04 (P1)** Help/onboarding overlay for controls.
- **FR-UI-05 (P2)** Graphs/charts (temperature over time, orbital distance over time).

---

## 6. Non-Functional Requirements
- **NFR-PERF-01** ≥ 60 FPS rendering with **100+ bodies** on a mid-range desktop GPU (MVP target).
- **NFR-PERF-02** Physics step must not block rendering (decoupled fixed-step loop; consider threading).
- **NFR-SCALE-01** Architecture must allow scaling to **10k+ bodies** via Barnes–Hut / GPU (Phase 4 target).
- **NFR-ACC-01** Conserve energy & momentum within a documented tolerance over a closed-system test run.
- **NFR-PORT-01** Windows 11 is the primary target; keep code OS-agnostic where practical.
- **NFR-USAB-01** A new user can spawn two bodies and see them orbit within 60 seconds, no manual.
- **NFR-MAINT-01** Physics core is engine-agnostic and unit-tested independently of rendering.
- **NFR-NUM-01** Use double precision; handle the huge dynamic range of mass/distance carefully
  (scaled units internally, e.g., SI or AU/solar-mass, documented and consistent).

---

## 7. Phased Roadmap (Milestones)

### Phase 0 — Foundations
- Project skeleton, venv, dependencies, window opens with Panda3D, render one sphere.
- Physics core module + pytest harness (two-body orbit matches analytic result).

### Phase 1 — MVP: N-Body Gravity Sandbox  *(the "clone the fun part" release)*
- FR-PHY-01..04, FR-BOD-01/02, FR-INT-01..04, FR-SIM-01/02,
  FR-CAM-01..04, FR-SCN-01/02, FR-UI-01/02.
- **Outcome:** spawn bodies in 3D, watch real orbits, collisions merge bodies,
  load the Solar System, save/load scenes, control time. Genuinely fun on its own.

### Phase 2 — Usability & Realism polish
- FR-PHY-05/06, FR-BOD-03/04, FR-INT-05..07, FR-SIM-03/04,
  FR-CAM-05..07, FR-SCN-03/04, FR-UI-03/04.
- **Decision checkpoint:** is Python performance sufficient, or port renderer to Godot?

### Phase 3 — Stars & Climate
- FR-PHY-07/08/09, FR-BOD-05, FR-CAM-08/09, FR-SCN-05, FR-UI-05.

### Phase 4 — Scale & Performance
- Barnes–Hut octree, GPU offload (CuPy/compute shaders), 10k+ bodies (NFR-SCALE-01).

### Phase 5 — Stretch
- Relativistic effects, VR, modding/scripting, richer materials & terrain.

---

## 8. High-Level Architecture

```
+-------------------+      +----------------------+      +------------------+
|   UI / Input      |<---->|   Simulation Core    |<---->|   Renderer       |
| (DirectGUI/imgui) |      | (engine-agnostic)    |      | (Panda3D scene)  |
| tools, panels,    |      | - Body store (SoA)   |      | - sphere nodes   |
| time controls     |      | - Integrator         |      | - trails         |
+-------------------+      | - Force solver       |      | - camera         |
                           | - Collision system   |      | - skybox/labels  |
                           | - Scenario load/save |      +------------------+
                           +----------------------+
```

Key principles:
- **Physics core has zero rendering dependencies** (testable headless).
- **Structure-of-Arrays** for body data (NumPy arrays: pos[N,3], vel[N,3], mass[N], ...)
  to keep the integrator vectorized and Numba/GPU-friendly.
- **Fixed-step physics, interpolated rendering**; sim time scale is independent of FPS.

---

## 9. Data Model (initial)

Internal: SoA NumPy arrays. Serialized scenario (JSON):

```json
{
  "version": 1,
  "units": { "length": "AU", "mass": "Msun", "time": "day" },
  "time_scale": 86400,
  "bodies": [
    {
      "name": "Sun", "type": "star",
      "mass": 1.0, "radius": 0.00465,
      "position": [0, 0, 0], "velocity": [0, 0, 0],
      "color": [1.0, 0.9, 0.6]
    },
    {
      "name": "Earth", "type": "planet",
      "mass": 3.003e-6, "radius": 4.26e-5,
      "position": [1, 0, 0], "velocity": [0, 0.0172, 0],
      "color": [0.2, 0.4, 1.0]
    }
  ]
}
```

(Unit system to be finalized in Phase 0 — SI vs AU/Msun/day — and applied consistently.)

---

## 10. Risks & Open Questions
- **R1 — Python physics performance** for large N. *Mitigation:* Numba + Barnes–Hut;
  Godot fallback; GPU path. *Open:* what N do we actually need for "fun"?
- **R2 — Numerical scale/precision** (mass ~1e30 kg, distance ~1e12 m, tiny dt).
  *Mitigation:* scaled internal units, double precision, leapfrog integrator.
- **R3 — Rendering huge scale ranges** (sun vs pebble in same view).
  *Mitigation:* logarithmic/clamped visual sizes, focus-relative camera.
- **R4 — Scope creep** (it's a full clone). *Mitigation:* ship Phase 1, gate the rest.
- **Q1 — Accuracy bar:** ✅ **Resolved — "looks right" wins.** Prioritize stable,
  plausible behavior and performance over scientific precision. Symplectic leapfrog
  integrator; no need to match ephemerides to the second.
- **Q2 — Aesthetic target:** ✅ **Resolved — photorealistic.** Real planet textures,
  PBR materials, HDR/bloom, atmospheric scattering (see §5.5 and §12).
- **Q3 — Data source:** ✅ **Resolved — see §12.** Mixed best-of-breed sources.

---

## 11. Definition of Done (Phase 1 / MVP)
- [x] Launch app → orbit-camera 3D view with starfield.
- [x] Load Solar System preset; planets orbit stably for many simulated years.
- [x] Spawn a new body by drag (position + velocity); it interacts gravitationally.
- [x] Select, edit (mass), and delete bodies live.
- [x] Two bodies on collision course merge, conserving mass & momentum.
- [x] Pause/play and change time rate.
- [x] Save scene to JSON and reload it identically.
- [x] Physics unit tests pass (two-body orbit, conservation within tolerance).
- [x] Physics sustains ≥ 60 FPS-equivalent with 100 bodies (~230 on the dev machine).

**Remaining polish before calling the MVP visually complete:** photoreal planet
textures (FR-CAM-04) — currently flat-shaded colours; and richer editing (velocity,
not just mass). Everything functional in the list above is implemented and tested.

---

## 12. Data & Asset Sources (Resolved)

Use the best source per data type rather than one catalog. All chosen for accuracy
+ permissive licensing suitable for bundling/redistribution.

### 12.1 Orbital state (positions & velocities)
- **JPL Horizons** (NASA/JPL) — authoritative state vectors for the Sun, planets,
  major moons, and many small bodies at a chosen epoch. Use it once to generate
  initial position/velocity for the Solar System preset, then bake into a JSON
  scenario (we don't query it at runtime).
  - Python access: `astroquery.jplhorizons` or the `Horizons` HTTP API.
  - Alternative for high accuracy over time: **JPL DE ephemerides** via `jplephem` /
    `astropy` + `skyfield` (only if "looks right" ever needs upgrading).

### 12.2 Physical constants (mass, radius, rotation, axial tilt, albedo)
- **NASA Planetary Fact Sheets** (nssdc.gsfc.nasa.gov) — clean, citable values for
  every planet/major moon. Hand-curate into a small bundled `bodies_catalog.json`.

### 12.3 Photoreal textures (the look)
- **Solar System Scope texture maps** — high-res planet/moon day maps, normal maps,
  cloud and ring textures; **CC BY 4.0** (redistributable with attribution). Primary.
- **NASA SVS / Visible Earth / USGS Astrogeology** — public-domain maps where higher
  fidelity or specific bodies are needed (Earth day/night/clouds, Moon, Mars, etc.).
- **HDRI starfield / Milky Way** skybox — NASA/ESO public-domain panoramas, or an
  ESO Milky Way panorama (check license) for the HDR background.

### 12.4 Licensing & attribution
- Keep a `CREDITS.md` / in-app credits listing every asset and its license.
- NASA imagery: generally public domain (verify per-asset).
- Solar System Scope: **must** attribute (CC BY 4.0).
- Bundle only redistributable assets; otherwise provide a download script.
```
