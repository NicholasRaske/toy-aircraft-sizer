# Modular RC Aircraft Configuration Advisor — Project Plan

**Status:** Planning
**Last updated:** 2026-08-15

---

## 1. Problem statement

A modular remote-control aircraft ships as a **constant fuselage** plus a small set of
interchangeable **wing** and **empennage** modules and an **extendable tail boom**.
Different combinations trade off speed, range, endurance, and manoeuvrability.

The pilot does not want to evaluate combinations. They want to state a mission and be told
what to build.

**Input**

| Field | Example |
|---|---|
| Mode | Loiter |
| Duration | 1 hour |
| Payload | 4 kg |

**Output — the assembly card**

> Fit **Surveyor** wings and the **Standard** empennage.
> Extend the tail to **340 mm**.
> Fuel **2.1 kg** — fill to **2.9 L**.
> Set CG **210 mm** aft of the nose; add **200 g** nose ballast.
> Predicted: 1 h 04 min loiter · 13.8 m/s stall · 12% static margin.

An expert must be able to open the same tool and see the aerodynamic numbers behind that
card. The novice sees an instruction; the expert sees a derivation.

### Operating context

| Parameter | Value |
|---|---|
| Class | RC / small UAS, petrol powered |
| All-up mass | Order of 10s of kg (typical: 20 kg) |
| Mission | Recreational flight and aerial photography over large farmland |
| Operating site | Large open fields |
| Onboard compute | Raspberry Pi class |
| Connectivity | **None. Fully offline at point of use.** |

> **Note on class:** at this mass the aircraft falls into a regulated category in most
> jurisdictions. The tool is a **sizing and prediction aid**, not an airworthiness
> approval. The UI must carry a disclaimer, and predictions must never be presented as
> flight-clearance.

---

## 2. Key consequences of the operating point

Five facts drive the whole design.

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

### 2.3 The mode defines the objective function

Aerial photography over farmland means the headline metric is not top speed. It is
**loiter endurance** and **area surveyed per tank**. Speed matters mainly as transit-to-site
time.

Rather than fixing one priority ordering, the pilot selects a **mode**, and the mode
selects the ranking function and the constraint set. Loiter and range are the primary
modes; speed and short-field are secondary.

### 2.4 The tool is prescriptive, not descriptive

This is the largest change from a pure analysis tool. The output is an instruction that
someone will physically build and then fly. Two consequences:

- **Flyability is a gate, not a warning.** A combination failing any rule in §4.10 must
  never be ranked or shown as an option. It is not "flagged"; it is excluded.
- **Recommendations must prefer margin.** Where two configurations score within a few
  percent, the one further from its nearest constraint boundary wins. A recommendation
  sitting exactly on the static-margin limit is technically valid and practically bad.

### 2.5 Offline and Pi-class compute — a weak constraint

The search space is **4 wings × 3 empennages = 12 combinations**, with tail extension
*solved* rather than searched (§4.9). A Raspberry Pi evaluates the whole space in
milliseconds.

So the compute constraint is effectively non-binding, and the plan should not be distorted
to respect it. **No optimiser, no heuristic search, no precomputed answer tables, no
cached grids.** Enumerate exhaustively and rank. Any design that trades flexibility for
speed here is solving a problem that does not exist.

What offline *does* constrain is packaging (§3.5): every dependency, polar and part file
must be vendored at build time, because a Pi in a field cannot `pip install`.

---

## 3. Architecture

### 3.1 Core principle

> The physics lives in a plain, importable Python package with **zero UI imports**.

Three entry points, all pure functions over plain data objects. No DOM, no framework, no
globals, no network I/O:

```python
analyze(config: Configuration) -> Results              # forward model
recommend(req: Requirements, cat: Catalog) -> Recommendation   # the product
envelope(mode: Mode, cat: Catalog) -> Envelope         # what is achievable at all
```

- **`analyze`** is unchanged from the original design and remains the foundation.
- **`recommend`** wraps it: enumerate the catalogue, solve tail extension, gate on
  flyability, rank by mode. It returns the assembly card *and* the `Results` for the
  chosen configuration, so progressive disclosure still works.
- **`envelope`** returns the achievable payload/duration frontier for a mode, so the UI
  can bound its own inputs before the pilot asks for something impossible (§4.11).

### 3.2 Stack decision

**Chosen: Streamlit**, unchanged — but the target is now a phone-sized card, not a desktop
dashboard.

Rationale — the stated priority is "as simple as possible". Streamlit collapses backend and
frontend into one Python file and provides sliders, dropdowns, tables, and charts with no
frontend code to maintain.

| | Streamlit (chosen) | FastAPI + static JS |
|---|---|---|
| Frontend code | None | HTML/CSS/JS to maintain |
| Charts | Built in | Library + wiring |
| Time to first output | Very short | Moderate |
| Layout control | Limited | Full |
| Path to polished product | Awkward | Clean |

Because the physics package has no UI dependency, migrating later costs only the shim. This
decision is **not** load-bearing.

Two new constraints on it:

- **Verify Streamlit's static assets resolve locally.** The core bundle is self-hosted, but
  any third-party component or web font is a CDN dependency and therefore disqualifying.
- **Decide the physical interface early.** A Pi in a field means either a small attached
  touchscreen or the Pi running a wifi hotspot with the pilot on a phone. This affects
  layout far more than the framework choice does.

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
│   ├── fuel.py                # fuel sizing loop: duration -> fuel mass and volume
│   ├── propulsion.py          # engine power curve incl. part-load BSFC; prop thrust
│   ├── aero.py                # drag buildup, CD = CD0 + k·CL²
│   ├── performance.py         # speeds, turns, climb, range, endurance
│   ├── stability.py           # neutral point, static margin, tail-extension solve
│   ├── rules.py               # flyability gate (hard pass/fail, was warnings.py)
│   ├── catalog.py             # part catalogue loading and validation
│   ├── config.py              # Configuration / Requirements / Results / Recommendation
│   ├── analyze.py             # analyze(config) -> Results
│   ├── recommend.py           # recommend(requirements, catalog) -> Recommendation
│   └── envelope.py            # envelope(mode, catalog) -> achievable frontier
├── parts/                     # data, not code
│   ├── wings.json
│   ├── empennages.json
│   ├── fuselage.json
│   ├── engines.json
│   └── polars/                # precomputed airfoil polars per part
├── tools/                     # dev-time only, never shipped to the aircraft
│   └── gen_catalog.py         # synthetic part-set generator for testing (§8.2)
├── tests/
├── app.py                     # Streamlit UI shim
├── requirements.txt           # fully pinned
├── wheelhouse/                # vendored wheels for offline install
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
- **Outputs are quantised to what the pilot can physically set.** The tail boom has
  detents; ballast comes in discrete weights; fuel is read off a graduated tank. An
  instruction of `extend to 347 mm` is unexecutable and therefore wrong — emit `340 mm`.
  Quantisation happens in the physics layer, and the *quantised* configuration is the one
  re-analysed for the reported performance.

### 3.5 Offline packaging

The aircraft never has a network. Therefore:

- `requirements.txt` fully pinned; wheels vendored into `wheelhouse/` and installed with
  `pip install --no-index --find-links wheelhouse`.
- Airfoil polars are **precomputed and shipped** (§4.2). XFOIL is a build-time tool, never
  a runtime dependency.
- Keep the dependency floor low. `numpy` is fine on a Pi. Avoid `scipy` if its only use is
  a root-find that is ten lines of bisection (§4.9).
- No telemetry, no update checks, no remote fonts or CDN assets.

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

**Mass is now an output, not an input.** The pilot states a duration; that determines the
fuel required; fuel is part of the mass:

$$m_{\text{total}} = m_{\text{empty}} + m_{\text{payload}} + m_{\text{fuel}}(\text{duration})$$

The 20 kg figure is no longer an assumption to be entered — it is a result.

### 4.5 Fuel sizing loop

Fuel burn depends on power required, which depends on total mass, which includes fuel.
This is a fixed point, solved by iteration:

1. Guess $m_{\text{fuel}}$.
2. Compute mass, then loiter (or cruise) power required.
3. Compute burn over the requested duration using part-load BSFC (§4.6).
4. Repeat until $m_{\text{fuel}}$ converges.

It converges in a handful of passes because fuel is a small fraction of all-up mass, making
the iteration strongly contractive. Add a reserve fraction (default 20%) before reporting.

**Output is a fill instruction, in volume.** The pilot fills a tank, not a mass budget:

$$V_{\text{fuel}} = m_{\text{fuel}} / \rho_{\text{fuel}}, \qquad \rho_{\text{petrol}} \approx 0.72\ \text{kg/L}$$

Quantise to the tank graduations. The aircraft knows its own **maximum fuel capacity —
assume 3.0 kg (≈ 4.2 L)** until confirmed. If the loop converges above capacity, or fails
to converge because each added kilogram of fuel costs more than it buys, the request is
infeasible on fuel and is handled per §4.11.

### 4.6 Propulsion
- Engine: brake power vs RPM curve, plus brake specific fuel consumption.
- Propeller: thrust and efficiency as a function of airspeed and RPM. Static thrust is a
  poor proxy — thrust falls off with forward speed and that determines max level speed.
- Available power at altitude scales with density.

> **BSFC must be a function of load fraction, not a constant.** This is the single largest
> accuracy risk in the plan, and it is aimed directly at the headline number.
>
> At 20 kg, $L/D \approx 12$, loiter near 16 m/s:
>
> $$P_{\text{shaft}} = \frac{W V}{(L/D)\,\eta_p} \approx \frac{196 \times 16}{12 \times 0.7} \approx 370\ \text{W}$$
>
> Against a 2.6 kW engine that is **~14% load**. Small two-strokes are far off their best
> BSFC there — real figures can be double the ~550 g/kWh nameplate, and there is a floor on
> idle fuel flow. A flat BSFC predicts roughly 0.2 kg/hr and an implausible 8+ hour
> endurance, so the tool would confidently promise loiter times it cannot deliver.
>
> Model BSFC as a curve against load fraction, with a minimum fuel-flow floor. Where the
> curve is unknown, err high: over-predicting fuel burn is safe, under-predicting strands
> an aircraft.

### 4.7 Aerodynamics
Finite-wing lift slope:

$$a = \frac{a_0}{1 + a_0 / (\pi \cdot AR \cdot e)}$$

Induced drag, with Oswald efficiency $e$ estimated from aspect ratio and taper:

$$C_{Di} = \frac{C_L^2}{\pi \cdot AR \cdot e}$$

Total drag polar from a component buildup (wing, tail, fuselage, landing gear, payload pod):

$$C_D = C_{D0} + k C_L^2$$

### 4.8 Performance
Everything below falls out of the polar plus available thrust:

- Stall speed: $V_s = \sqrt{2W / (\rho S C_{L,max})}$
- Max level speed: thrust-available equals thrust-required intersection
- Best glide: $L/D_{max} = \tfrac{1}{2}\sqrt{\pi \cdot AR \cdot e / C_{D0}}$
- Minimum sink rate and best-endurance speed
- Rate of climb from excess power
- Turn radius $r = V^2 / (g\sqrt{n^2 - 1})$ and max sustained turn rate
- Range and endurance via Breguet, integrated over fuel burn

### 4.9 Stability, trim, and the tail-extension solve
This is what makes the tool usable by a non-expert.

- Horizontal tail volume $V_H = \dfrac{S_t \, l_t}{S \, \bar{c}}$ — target roughly 0.4–0.7
- Vertical tail volume $V_V = \dfrac{S_v \, l_v}{S \, b}$ — target roughly 0.02–0.05
- Neutral point from wing plus tail contributions
- Static margin $= (x_{np} - x_{cg}) / \bar{c}$ — target 10–15% for this class
- **Required CG position and permissible CG range for each combination** — the single most
  valuable output, and now an *instruction* rather than a readout
- CG excursion as fuel burns, checked against the permissible range

**The extendable tail is solved, not searched.** Extending the boom lengthens $l_t$, which
moves the neutral point aft faster than it moves the CG aft — the boom and empennage are
light, while the aero contribution scales with $V_H \propto l_t$. Static margin is
therefore **monotonically increasing** in extension.

So for each (wing, empennage) pair, bisect on extension to hit the target static margin.
Monotonicity makes bisection unconditionally reliable and removes any need for `scipy`.
The continuous variable costs one cheap inner loop, not a third catalogue dimension:

> **12 outer configurations × one 1-D bisection each.** That is the entire search.

Where the solve lands outside the boom's physical travel, clamp to the limit and let the
gate decide; where it lands inside, quantise to the nearest detent and re-analyse.

### 4.10 The flyability gate
The tool must **validate** combinations, not merely score them. Because the output is now
an instruction to build, these are **hard pass/fail filters applied before ranking** — a
failing combination is excluded from consideration entirely, never shown with a flattering
L/D and a caveat.

- Static margin outside safe band (negative, or excessively large)
- CG cannot be placed in range with available ballast
- CG leaves permissible range as fuel burns
- Tail volume coefficient below minimum
- Required fuel exceeds tank capacity (§4.5)
- Stall speed too high for the intended field
- Wing loading outside sane bounds
- Insufficient thrust for level flight or safe climb

Each rule returns a structured reason, not a string. Reasons drive both the expert view and
the infeasibility explanation in §4.11.

### 4.11 Ranking and the feasible envelope

**Ranking.** Each mode supplies an objective and any mode-specific constraints:

| Mode | Objective | Also constrained on |
|---|---|---|
| Loiter | Maximise endurance | Hectares per tank |
| Range | Maximise still-air range | Cruise speed floor |
| Speed | Maximise max level speed | Stall speed ceiling |
| Short-field | Minimise stall speed | Climb gradient |

Ties within a few percent are broken by **constraint margin** (§2.4), then by a stable
deterministic key so the same request always yields the same card.

**Bound the input rather than rejecting it.** `envelope(mode, catalog)` returns the
achievable payload/duration frontier for a mode, computed by sweeping the catalogue once.
The UI uses it to set slider limits the moment a mode is chosen, so most impossible
requests simply cannot be expressed.

Note the frontier is a **curve, not a pair of independent maxima** — payload and duration
trade against each other, so max payload and max duration are not simultaneously
available. Sliders must therefore re-clamp against each other as they move, and the UI
should show the frontier rather than only enforcing it.

**Residual infeasibility still needs a graceful answer**, because field elevation, reserve
fraction and payload placement can push a request outside the envelope after the fact.
Never return an error or an empty result. Relax one requirement at a time and report which
one binds:

> Not achievable with 4.0 kg payload.
> Closest: **52 min** with Surveyor + Standard.
> For the full hour, reduce payload to **3.2 kg** — limited by tank capacity.

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

### 5.2 Empennages

| Name | Character |
|---|---|
| **Standard** | Large tail volume, long arm. Forgiving and stable. |
| **Compact** | Short arm, small area. Responsive, less stable. |
| **V-tail** | Lighter, less wetted area, coupled control. |

Four wings × three empennages = **twelve combinations**. Enough to be interesting; few
enough that every combination can be hand-checked during validation.

### 5.3 Extendable tail boom

| Parameter | Assumed value |
|---|---|
| Travel | 0–400 mm beyond the nominal position |
| Detents | Every 10 mm |

Not a catalogue dimension — it is the trim mechanism, solved per §4.9. Both figures are
placeholders pending §10 Q2.

### 5.4 Baseline defaults

| Parameter | Default |
|---|---|
| Engine | 30 cc two-stroke petrol, ~2.6 kW |
| BSFC | Load-dependent curve; ~550 g/kWh at best point (§4.6) |
| Propeller | 22 × 8 |
| **Max fuel capacity** | **3.0 kg (≈ 4.2 L)** — a hard limit, not a default |
| Fuel reserve | 20% |
| Empty mass (fuselage + engine) | ~12 kg |
| Payload | Pilot input; 1.5 kg camera and gimbal typical |
| Field elevation | Sea level, 15 °C |

Note what is **no longer** here: all-up mass and fuel load. Both are computed (§4.4, §4.5).
All-up mass around 20 kg should emerge as a result — if it does not, something is wrong.

Maximum fuel capacity is a **property of the airframe**, not a tunable. It participates in
the gate (§4.10) and bounds the envelope (§4.11).

---

## 6. Pilot interface

Progressive disclosure, but the top layer is now a single instruction rather than a
dashboard. Assume a phone-sized screen in bright sunlight.

### 6.1 Input

1. **Mode** dropdown — chosen first, because it sets everything downstream.
2. **Sliders** for duration and payload, **bounded by `envelope(mode)`** and re-clamping
   against each other as they move (§4.11).
3. **Field elevation and temperature**, defaulted, collapsed.

### 6.2 Output — the assembly card

The primary and often only thing shown. Ordered by assembly sequence, not by importance:

| Line | Example |
|---|---|
| Wings | Surveyor |
| Empennage | Standard |
| Tail extension | 340 mm |
| **Fuel fill** | **2.9 L (2.1 kg)** |
| CG target | 210 mm from nose |
| Ballast | 200 g nose |
| Prediction | 1 h 04 min · 13.8 m/s stall · SM 12% |

Below it, one line of reasoning and the runner-up:

> Chosen for endurance. Next best: Sport + Standard, 8 min shorter.

This replaces A/B comparison mode at a fraction of the cost — the tool has already done the
comparison, so it should show its working rather than make the pilot redo it.

### 6.3 Details view (collapsed by default)

Everything from the original dashboard design, demoted behind an expander:

| Panel | Contents |
|---|---|
| **Envelope** | Stall speed, best cruise, max level speed, never-exceed |
| **Efficiency** | $L/D_{max}$, best glide speed, minimum sink, power-required curve |
| **Mission** | Loiter endurance, still-air range, hectares surveyed per tank |
| **Agility** | Min turn radius, max sustained turn rate, roll rate estimate, load factor |
| **Balance** | CG envelope with green band, static margin, $V_H$/$V_V$ gauges, CG shift as fuel burns |
| **Rejected** | Combinations excluded by the gate, with the binding rule for each |

Visuals — radar chart, drag polar, power-required curve, planform preview — live here too.
The **Rejected** panel is new and matters: an expert's first question about any
recommendation is what it beat and why the others were dropped.

---

## 7. Milestones

| # | Milestone | Definition of done |
|---|---|---|
| 0 | **Catalogue generator** | `tools/gen_catalog.py` emits valid synthetic part sets; unblocks test-first work on everything below |
| 1 | **Schema and parts** | `Configuration`/`Requirements`/`Results`/`Recommendation` defined; twelve parts plus boom travel encoded as JSON; a baseline catalogue loads and validates |
| 2 | **Forward physics** | All modules test-first, validated against hand calculations and one known real airframe. Includes **part-load BSFC** and the **fuel sizing loop** |
| 3 | **Tail-extension solve** | Bisection on static margin, with monotonicity asserted by test |
| 4 | **Recommender** | Enumerate → gate → rank → assembly card, as **plain text**. Ugly but end to end |
| 5 | **Envelope and infeasibility** | `envelope(mode)` bounds the inputs; nearest-feasible fallback names the binding constraint |
| 6 | **Pilot UI** | Assembly card on a phone-sized screen; details and rejected combinations behind expanders |
| 7 | **Offline packaging** | Vendored wheelhouse; verified install and run on a clean Pi with networking disabled |

Milestone 4 keeps the original spirit of "milestone 3 is deliberately ugly" — close the
loop in plain text before any UI exists, so schema problems surface while they are still
cheap to fix.

Milestone 0 is new and comes first because the validation strategy in §8 depends on it.
Milestone 7 is not a formality: an offline install is the kind of thing that is discovered
to be broken at the field, and it should be proven on real hardware.

---

## 8. Validation strategy

Accuracy is the product. Predictions that are quietly wrong are worse than no tool — and
now that the tool issues build instructions, a quiet error becomes a physical one.

### 8.1 Forward model

- **Unit tests** on every physics function with hand-computed expected values
- **Known-airfoil checks** — e.g. NACA 2412 zero-lift angle should land near −2.1°
- **Known-airframe check** — feed in a real aircraft of similar class and compare predicted
  stall speed, cruise, and L/D against published figures
- **Sanity bounds** — assert stall speeds, wing loadings, and L/D fall in physically
  plausible ranges for all twelve combinations
- **Monotonicity checks** — higher aspect ratio must improve L/D; more area must reduce
  stall speed; static margin must increase with tail extension. Catches sign errors that
  spot-checks miss.
- **Fuel loop convergence** — converges from any starting guess, and the converged mass
  reproduces the requested duration when fed back through the forward model.

### 8.2 Synthetic catalogue generator

`tools/gen_catalog.py` generates randomised but physically plausible part sets — wings
across a span of aspect ratios and areas, empennages across arms and areas, engines across
power and BSFC curves. It is a **development tool, not shipped to the aircraft**.

It exists because twelve hand-authored parts are far too few to test a recommender. Twelve
combinations cannot exercise tie-breaking, gate coverage, envelope shape, or the corners
where the fuel loop fails to converge. Generating hundreds of catalogues does.

It should support seeded, reproducible output so a failing case can be replayed exactly,
and deliberately degenerate sets — every combination unflyable, two combinations exactly
tied, tail travel insufficient for any solve — to prove the failure paths.

### 8.3 Recommender properties

These are property tests over generated catalogues, not example tests:

- **The gate is never bypassed.** No recommendation ever violates a §4.10 rule. This is the
  single most important test in the suite.
- **Determinism.** Identical requirements and catalogue yield an identical card, including
  tie-breaks.
- **Monotonic response.** More payload never increases recommended endurance; a longer
  requested duration never decreases recommended fuel.
- **Envelope agreement.** Any request inside `envelope(mode)` returns a feasible
  recommendation; any request outside returns a fallback naming a binding constraint.
  Disagreement between the two means one of them is wrong.
- **Quantisation is honest.** Reported performance is computed from the quantised,
  buildable configuration — never from the unquantised solve.
- **Never empty.** Every request returns either a card or a named nearest-feasible
  alternative. No exceptions, no empty results.

---

## 9. Out of scope for v1

- Structural analysis, spar sizing, flutter, or load limits
- Control surface sizing and control authority
- Full 6-DOF dynamic stability (phugoid, dutch roll, spiral modes)
- Vortex-lattice or CFD solvers — analytic plus tabulated polars is sufficient at this
  fidelity
- Autopilot, flight planning, or survey path generation
- Compressibility effects (irrelevant at these speeds)
- **A/B comparison mode.** Cut deliberately. The tool now chooses, and §6.2 shows the
  runner-up with a reason — which is what comparison mode was actually for.
- **Optimisation machinery.** Twelve combinations with a 1-D inner solve does not warrant
  it (§2.5).
- Wind, turbulence, and non-still-air mission planning

---

## 10. Open questions

Ordered by how expensive they are to answer late.

1. **Is the engine fixed, or a fourth module?** Affects the `Configuration` schema and the
   size of the search, so it lands in Milestone 1. Cheapest to decide now.
2. **Boom travel and detent spacing**, and whether each empennage has its own travel range.
   Sets output quantisation (§3.4) and the bisection bounds (§4.9).
3. **Is the tail-extension solve sufficient on its own, or is ballast still required?** If
   extension alone can trim the CG, the ballast line leaves the assembly card entirely.
4. **Tank position relative to CG** — a tank far from the CG makes fuel-burn CG travel much
   worse, and that travel is now checked by the gate rather than merely displayed.
5. **Part-load BSFC data for the engine.** The §4.6 risk is only retired by real numbers.
   Absent them, assume pessimistically.
6. Camera and gimbal mass and mounting position.
7. Which modes ship in v1 beyond loiter and range.
8. Whether the tool should also *size* wings from a target wing loading, or only select
   from the fixed part set.

---

## 11. Design principles (summary)

1. **Physics is pure and UI-free.** `analyze`, `recommend`, `envelope` — plain functions
   over plain data.
2. **The output is an instruction, not a report.** The pilot states a mission and is told
   what to build.
3. **SI internally, convert only at the display edge.**
4. **Parts are data, not code.**
5. **Flyability is a gate, not a warning.** Unflyable combinations are excluded, never
   ranked with a caveat.
6. **Bound the input rather than rejecting it.** Make impossible requests hard to express;
   answer the ones that slip through with the nearest feasible alternative.
7. **Only emit instructions the pilot can execute.** Quantise to real detents, real weights,
   real tank graduations — and report performance for the quantised build.
8. **Solve what is monotonic; enumerate what is small.** Neither warrants an optimiser.
9. **Mass and inertia matter as much as aerodynamics.** Swapping a wing moves the CG.
10. **Progressive disclosure.** One card on top, expert numbers underneath.
11. **Accuracy is the product.** Every number is defensible or it is not shown. Where data
    is missing, err in the direction that strands no one.
