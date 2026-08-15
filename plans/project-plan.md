# Modular RC Aircraft Sizing Dashboard — Project Plan

**Status:** Planning
**Last updated:** 2026-08-15

---

## 1. Problem statement

Build a dashboard for a modular remote-control aircraft. The airframe ships with a
**constant fuselage** and a **set of interchangeable wing and tail modules**. Different
combinations trade off speed, range, endurance, and manoeuvrability.

A non-expert must be able to plug modules together and immediately understand:

- What the aircraft will do (how fast, how far, how long, how tightly it turns)
- Whether the combination is **safe to fly**
- Where to put the CG to make it fly correctly

An expert must be able to open the same tool and see the underlying aerodynamic numbers.

### Operating context

| Parameter | Value |
|---|---|
| Class | RC / small UAS, petrol powered |
| All-up mass | Order of 10s of kg (baseline: 20 kg) |
| Mission | Recreational flight and aerial photography over large farmland |
| Operating site | Large open fields |

> **Note on class:** at this mass the aircraft falls into a regulated category in most
> jurisdictions. The tool is a **sizing and prediction aid**, not an airworthiness
> approval. The UI must carry a disclaimer, and predictions must never be presented as
> flight-clearance.

---

## 2. Key consequences of the operating point

Three facts about this scale drive the whole design.

### 2.1 Reynolds number is friendly

With a chord around 0.4 m at 20–25 m/s:

$$Re = \frac{\rho V c}{\mu} \approx \frac{1.225 \times 22 \times 0.42}{1.81\times10^{-5}} \approx 6\times10^{5}$$

This is comfortably inside the range where published NACA data and XFOIL are reliable.
The low-Reynolds-number accuracy problems that plague small foam models do not apply here.
**This is the single biggest de-risking factor in the project.**

### 2.2 Fuel is a first-class variable

Unlike a battery, fuel mass burns off during flight. The aircraft gets lighter *and the
CG moves*. Therefore:

- Performance must be evaluated at more than one mass point (takeoff, mid, dry)
- Breguet range and endurance equations are genuinely appropriate, not an approximation
- **CG travel due to fuel burn is a required output.** It is the thing most builders get
  wrong, and at this mass getting it wrong is expensive.

### 2.3 The mission defines the objective function

Aerial photography over farmland means the headline metric is not top speed. It is
**loiter endurance** and **area surveyed per tank**. Speed matters mainly as transit-to-site
time. The dashboard should reflect this priority ordering.

---

## 3. Architecture

### 3.1 Core principle

> The physics lives in a plain, importable Python package with **zero UI imports**.

Everything flows from one entry point:

```python
analyze(config: Configuration) -> Results
```

`config` fully describes the assembled aircraft. `Results` is a plain data object. No DOM,
no framework, no globals, no I/O. This makes the physics unit-testable, makes the dashboard
a thin shim, and makes the UI choice reversible.

### 3.2 Stack decision

**Chosen: Streamlit.**

Rationale — the stated priority is "as simple as possible". Streamlit collapses backend and
frontend into one Python file and provides sliders, dropdowns, tables, and charts with no
frontend code to maintain.

| | Streamlit (chosen) | FastAPI + static JS |
|---|---|---|
| Frontend code | None | HTML/CSS/JS to maintain |
| Charts | Built in | Library + wiring |
| Time to first dashboard | Very short | Moderate |
| Layout control | Limited | Full |
| Path to polished product | Awkward | Clean |

Because the physics package has no UI dependency, migrating to FastAPI + a JS frontend
later costs only the shim. This decision is **not** load-bearing.

### 3.3 Layout

```
ToyAircraftSizer/
├── plans/
│   └── project-plan.md
├── aerosizer/                 # pure physics — no UI imports
│   ├── __init__.py
│   ├── units.py               # SI internally; conversion only at display edge
│   ├── atmosphere.py          # ISA density, viscosity, altitude effects
│   ├── airfoil.py             # NACA 4-digit decode; polar lookup + analytic fallback
│   ├── geometry.py            # planform: area, AR, MAC, taper, sweep
│   ├── mass.py                # assembly mass, CG, inertia, fuel-burn CG shift
│   ├── propulsion.py          # engine power curve, prop thrust vs airspeed
│   ├── aero.py                # drag buildup, CD = CD0 + k·CL²
│   ├── performance.py         # speeds, turns, climb, range, endurance
│   ├── stability.py           # neutral point, static margin, tail volumes
│   ├── warnings.py            # flyability rules and rule violations
│   ├── config.py              # Configuration / Results dataclasses
│   └── analyze.py             # analyze(config) -> Results
├── parts/                     # data, not code
│   ├── wings.json
│   ├── tails.json
│   ├── fuselage.json
│   ├── engines.json
│   └── polars/                # precomputed airfoil polars per part
├── tests/
├── app.py                     # Streamlit dashboard
├── requirements.txt
└── venv/
```

### 3.4 Conventions

- **SI units internally, always.** Metres, kilograms, seconds, newtons, radians.
  Conversion to display units happens only in the UI layer. Unit mixing is the classic
  failure mode for this kind of tool.
- **Parts are data, not code.** Adding a wing means adding a JSON entry, never editing a
  module.
- **Angles in radians internally**, degrees at the display edge.
- **All coordinates relative to a fuselage datum** (nose tip), positive aft.

---

## 4. Physics model

Built in dependency order. Each stage is independently testable.

### 4.1 Atmosphere
ISA density and dynamic viscosity as a function of altitude. Field elevation and
temperature are user inputs, since density altitude materially changes stall speed and
engine power.

### 4.2 Airfoil
A NACA 4-digit code decodes to max camber $m$, camber position $p$, and thickness $t$.

- **Primary path:** precomputed XFOIL polars shipped as lookup tables, one per airfoil in
  the part set, at representative Reynolds numbers with interpolation between them.
  Since the part set is fixed and small, this is cheap and accurate.
- **Fallback path:** thin-airfoil theory for arbitrary user-entered NACA codes. Gives
  zero-lift angle $\alpha_{L0}$ from the camber line and $C_{l\alpha} \approx 2\pi$ per
  radian. Profile drag from a skin-friction plus form-factor estimate.

### 4.3 Geometry
From span, root chord, tip chord, sweep, dihedral, and incidence: reference area $S$,
aspect ratio $AR$, taper ratio $\lambda$, mean aerodynamic chord $\bar{c}$ and its
longitudinal position.

### 4.4 Mass and balance
Each module carries a mass and a centroid position. The assembly sums to an all-up mass and
CG. Roll and pitch inertia are estimated from module mass distribution — this matters
because *agility is as much an inertia story as an aerodynamic one*.

Fuel is modelled as a mass at the tank position that varies from full to empty.

### 4.5 Propulsion
- Engine: brake power vs RPM curve, plus brake specific fuel consumption (BSFC).
- Propeller: thrust and efficiency as a function of airspeed and RPM. Static thrust is a
  poor proxy — thrust falls off with forward speed and that determines max level speed.
- Available power at altitude scales with density.

### 4.6 Aerodynamics
Finite-wing lift slope:

$$a = \frac{a_0}{1 + a_0 / (\pi \cdot AR \cdot e)}$$

Induced drag, with Oswald efficiency $e$ estimated from aspect ratio and taper:

$$C_{Di} = \frac{C_L^2}{\pi \cdot AR \cdot e}$$

Total drag polar from a component buildup (wing, tail, fuselage, landing gear, payload pod):

$$C_D = C_{D0} + k C_L^2$$

### 4.7 Performance
Everything below falls out of the polar plus available thrust:

- Stall speed: $V_s = \sqrt{2W / (\rho S C_{L,max})}$
- Max level speed: thrust-available equals thrust-required intersection
- Best glide: $L/D_{max} = \tfrac{1}{2}\sqrt{\pi \cdot AR \cdot e / C_{D0}}$
- Minimum sink rate and best-endurance speed
- Rate of climb from excess power
- Turn radius $r = V^2 / (g\sqrt{n^2 - 1})$ and max sustained turn rate
- Range and endurance via Breguet, integrated over fuel burn

### 4.8 Stability and trim
This is what makes the tool usable by a non-expert.

- Horizontal tail volume $V_H = \dfrac{S_t \, l_t}{S \, \bar{c}}$ — target roughly 0.4–0.7
- Vertical tail volume $V_V = \dfrac{S_v \, l_v}{S \, b}$ — target roughly 0.02–0.05
- Neutral point from wing plus tail contributions
- Static margin $= (x_{np} - x_{cg}) / \bar{c}$ — target 10–15% for this class
- **Required CG position and permissible CG range for each combination** — the single most
  valuable output
- CG excursion as fuel burns, checked against the permissible range

### 4.9 Warnings and flyability
The tool must **validate** combinations, not merely score them. A combination that is
statically unstable must be reported as unflyable, not awarded a flattering L/D. Rules to
implement:

- Static margin outside safe band (negative, or excessively large)
- CG cannot be placed in range with available ballast
- CG leaves permissible range as fuel burns
- Tail volume coefficient below minimum
- Stall speed too high for the intended field
- Wing loading outside sane bounds
- Insufficient thrust for level flight or safe climb

---

## 5. Part set

Deliberately small and simple for v1, but spread wide enough that the choice visibly
matters. Baseline all-up mass 20 kg.

### 5.1 Wings

| Name | AR | Area (m²) | Span (m) | Airfoil | Character |
|---|---|---|---|---|---|
| **Surveyor** | 9 | 1.6 | 3.8 | NACA 4412 | Long endurance, efficient, stable. The camera wing. |
| **Sport** | 6 | 1.3 | 2.8 | NACA 2412 | Balanced all-rounder. |
| **Dash** | 4.5 | 1.0 | 2.1 | NACA 2409, tapered | Fast, high wing loading, high stall speed. |
| **Hauler** | 7 | 2.0 | 3.7 | NACA 6412 | Slow, short-field, heavy payload. |

Expected stall speeds at 20 kg, sea level: Surveyor ≈ 12 m/s, Sport ≈ 14 m/s,
Dash ≈ 16 m/s, Hauler ≈ 10 m/s. These are sanity targets for validation, not outputs.

### 5.2 Tails

| Name | Character |
|---|---|
| **Standard** | Large tail volume, long arm. Forgiving and stable. |
| **Compact** | Short arm, small area. Responsive, less stable. |
| **V-tail** | Lighter, less wetted area, coupled control. |

Four wings × three tails = **twelve combinations**. Enough to be interesting; few enough
that every combination can be hand-checked during validation.

### 5.3 Baseline defaults (all tunable in the UI)

| Parameter | Default |
|---|---|
| All-up mass | 20 kg |
| Engine | 30 cc two-stroke petrol, ~2.6 kW |
| BSFC | ~550 g/kWh |
| Propeller | 22 × 8 |
| Fuel capacity | 2.5 L (~1.8 kg) |
| Payload | 1.5 kg camera and gimbal |
| Field elevation | Sea level, 15 °C |

Rather than asking the user to supply these up front, the tool ships with these defaults
and exposes them as sliders. **Guessing these well is exactly what the tool is for.**

---

## 6. Dashboard design

Progressive disclosure: plain-language summary on top, numbers underneath, full polars
behind an "Advanced" expander.

### 6.1 Panels

| Panel | Contents |
|---|---|
| **Envelope** | Stall speed, best cruise, max level speed, never-exceed |
| **Efficiency** | $L/D_{max}$, best glide speed, minimum sink, power-required curve |
| **Mission** | Loiter endurance, still-air range, hectares surveyed per tank |
| **Agility** | Min turn radius, max sustained turn rate, roll rate estimate, load factor |
| **Balance** | CG envelope with green band, static margin, $V_H$/$V_V$ gauges, CG shift as fuel burns |
| **Warnings** | Unstable, CG-infeasible, or otherwise unflyable combinations |

### 6.2 Visual elements

- Radar chart summarising Speed / Range / Endurance / Agility / Stability
- Drag polar and power-required curves
- Planform preview drawn from the actual geometry
- CG slider with a green permissible band and a marker showing fuel-burn travel

### 6.3 Interaction

- Two dropdowns (wing, tail) drive everything
- Sliders for mass, payload, fuel, field elevation
- A/B comparison mode for two configurations side by side

---

## 7. Milestones

| # | Milestone | Definition of done |
|---|---|---|
| 1 | **Schema and parts** | `Configuration`/`Results` dataclasses defined; twelve parts encoded as JSON; a baseline config loads and validates |
| 2 | **Physics core** | All modules implemented test-first; results validated against hand calculations and at least one known real airframe |
| 3 | **Minimal dashboard** | Two dropdowns and one metric table in Streamlit — proves the loop closes end to end |
| 4 | **Full dashboard** | Charts, radar, CG band, warnings panel, tunable defaults |
| 5 | **Comparison** | A/B two configurations side by side; shareable/exportable configuration |

Milestone 3 is deliberately ugly. Closing the loop early surfaces schema problems while
they are still cheap to fix.

---

## 8. Validation strategy

Accuracy is the product. Predictions that are quietly wrong are worse than no tool.

- **Unit tests** on every physics function with hand-computed expected values
- **Known-airfoil checks** — e.g. NACA 2412 zero-lift angle should land near −2.1°
- **Known-airframe check** — feed in a real aircraft of similar class and compare predicted
  stall speed, cruise, and L/D against published figures
- **Sanity bounds** — assert stall speeds, wing loadings, and L/D fall in physically
  plausible ranges for all twelve combinations
- **Monotonicity checks** — higher aspect ratio must improve L/D; more area must reduce
  stall speed. Catches sign errors that spot-checks miss.

---

## 9. Out of scope for v1

- Structural analysis, spar sizing, flutter, or load limits
- Control surface sizing and control authority
- Full 6-DOF dynamic stability (phugoid, dutch roll, spiral modes)
- Vortex-lattice or CFD solvers — analytic plus tabulated polars is sufficient at this
  fidelity
- Autopilot, flight planning, or survey path generation
- Compressibility effects (irrelevant at these speeds)

---

## 10. Open questions

Non-blocking — all have sensible defaults in §5.3, but worth confirming:

1. Fuselage tank position relative to the CG — a tank far from the CG makes fuel-burn CG
   travel much worse.
2. Camera and gimbal mass and mounting position.
3. Whether a fixed engine is assumed, or engine choice is a fourth configurable module.
4. Whether the tool should also *size* wings from a target wing loading, or only analyse
   the fixed part set.

---

## 11. Design principles (summary)

1. **Physics is pure and UI-free.** One `analyze(config)` entry point.
2. **SI internally, convert only at the display edge.**
3. **Parts are data, not code.**
4. **Validate combinations, do not merely score them.** Unflyable must be reported as
   unflyable.
5. **Mass and inertia matter as much as aerodynamics.** Swapping a wing moves the CG.
6. **Progressive disclosure.** Novice-readable on top, expert numbers underneath.
7. **Accuracy is the product.** Every number is defensible or it is not shown.
