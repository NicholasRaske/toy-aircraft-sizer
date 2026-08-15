# Modular RC Aircraft Configuration Advisor

State a mission, get told what to build.

The pilot enters a mode, a duration and a payload. The tool enumerates every
wing and empennage combination in the catalogue, evaluates each one, and
returns an **assembly card** — the parts to fit, how far to extend the tail,
how much fuel to pour in, and where to set the centre of gravity.

See [plans/project-plan.md](plans/project-plan.md) for the design.

> **This is a sizing and prediction aid, not an airworthiness approval.**
> It confers no flight clearance. See *Build state* below for what the numbers
> are currently worth.

## Setup

Python 3.11 or later. The physics package has no runtime dependencies; pytest
is the only development dependency.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running it

```bash
python main.py --mode loiter --duration 1.0 --payload 4.0
```

| Option | Meaning | Default |
|---|---|---|
| `--mode` | `loiter`, `range`, `speed` or `short_field` | `loiter` |
| `--duration` | requested flight time, in **hours** | `1.0` |
| `--payload` | payload mass, in **kilograms** | `4.0` |
| `--parts` | directory holding the part catalogue | `./parts` |

Every option has a default, so bare `python main.py` produces a card.

## Tests

```bash
python -m pytest -q
```

## Using it as a library

The physics is a plain importable package with zero UI imports.

```python
from pathlib import Path
from aerosizer import FlightMode, Requirements, load_catalog, recommend, render_assembly_card

catalog = load_catalog(Path("parts"))
requirements = Requirements(mode=FlightMode.LOITER, duration=3600.0, payload_mass=4.0)

print(render_assembly_card(recommend(requirements, catalog)))
```

Two entry points, both pure functions over plain data:

- `analyze(configuration) -> Results` — the forward model. Evaluates one fully
  determined aircraft. It never solves for anything.
- `recommend(requirements, catalog) -> Recommendation` — the product.
  Enumerates, ranks, and returns the chosen configuration with its runner-up.

Every iterative solve in this project — fuel mass for a requested duration,
tail extension for a target static margin — lives in `recommend`, expressed as
repeated calls to `analyze`.

## Conventions

- **SI throughout.** Metres, kilograms, seconds, newtons, radians. Conversion
  happens only at the edges: in `catalog.py` when data is read, and in
  `assembly_card.py` when a number is shown.
- **Parts are data.** Adding a wing means adding a JSON entry in `parts/`,
  never editing a module. Catalogue keys carry explicit unit suffixes
  (`span_m`, `mass_kg`) because JSON has no other way to declare units.
- **Stations** are measured in metres aft of the nose datum, positive aft.

## Adding a part

Add an entry to `parts/wings.json` or `parts/empennages.json` and it is picked
up on the next run. The catalogue loader is deliberately strict — a malformed
part fails loudly at load time rather than producing a plausible and wrong
card in a field.

## Build state

This is being built as a tracer bullet: a thin end-to-end slice first, then
thickened one pass at a time. The current state is **B1**.

| Step | Adds | Status |
|---|---|---|
| B1 | Schemas, catalogue, enumerate → rank → card | done |
| B2 | Mass rollup, centre of gravity, real stall speed | next |
| B3 | Drag polar, lift-to-drag, endurance | |
| T1 | Fuel sizing loop; mass becomes derived | |
| T2 | Static margin and the tail-extension solve | |
| T3 | The flyability gate | |
| T4 | Achievable envelope and infeasibility fallback | |
| T5 | Part-load fuel consumption, real polars, atmosphere | |
| T6 | Streamlit interface | |
| T7 | Offline packaging, verified on a Raspberry Pi | |

**Every number `analyze` returns is currently a placeholder.** They are shaped
so that ranking and rendering can be exercised end to end, but they are not
physics. There is also no flyability gate yet, so the tool will happily
recommend a combination that cannot be trimmed or cannot climb. The assembly
card says so, in a banner, until that changes.
