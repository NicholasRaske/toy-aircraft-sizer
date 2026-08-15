# Modular RC Aircraft Configuration Advisor

State a mission, get told what to build.

The pilot picks a mode and states the mission in its own terms — how far to the
site and how long on station, or simply how far. The tool enumerates every wing
and empennage combination in the catalogue, flies each one over that mission,
and returns an **assembly card**: the parts to fit, how far to extend the tail,
how much fuel the mission burns, and where to set the centre of gravity.

It also reports the speeds worth flying — stall, best endurance, best range,
maximum level, best climb — each with whatever is limiting it.

See [plans/project-plan.md](plans/project-plan.md) for the overall design and
[plans/phase-2-mission-and-performance.md](plans/phase-2-mission-and-performance.md)
for the current phase.

> **This is a sizing and prediction aid, not an airworthiness approval.**
> It confers no flight clearance. See *Build state* below for what the numbers
> are currently worth — they are not yet worth much.

## Setup

Python 3.11 or later.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The physics package has **no runtime dependencies at all** — it is pure
standard library, and a test enforces that. `requirements.txt` carries only
pytest and ruff.

Tk is needed for the kiosk. It ships with Python on Windows and macOS; on
Debian or Raspberry Pi OS, `sudo apt install python3-tk`.

### Development extras

The demonstration and the catalogue generator use AeroSandbox, which is a large
dependency and deliberately **not** in `requirements.txt`:

```bash
pip install aerosandbox
```

Nothing that runs on the aircraft needs it. See *Build-time tools* below.

## Running it

### Demonstration

The kiosk and the aircraft it is describing, side by side. Change the mission
and watch both respond.

```bash
python demo.py
```

Two windows, one event loop. Requires AeroSandbox. Closing either window ends
the demonstration.

### Kiosk screen

The aircraft-mounted display: a panel sized for a 3.5 inch screen, with large
touch targets and no browser anywhere in the stack. This is what would fly.

```bash
python kiosk.py                # windowed, at true panel size (480x320)
python kiosk.py --fullscreen   # on the aircraft; Escape exits
```

One row per input, cycled with `<` and `>`. Two pages: **ASSEMBLY** for what to
build, **SPEEDS** for what it will do.

### Command line

```bash
python main.py --mode loiter --transit-distance 12 --station-time 90
python main.py --mode return_range --distance 40 --payload 3
```

Arguments are built from whichever fields the chosen mode declares, so they
differ by mode. Values are given in the units a pilot would say aloud and
converted to SI on the way in.

| Option | Applies to | Unit | Default |
|---|---|---|---|
| `--mode` | all | `loiter`, `one_way_range`, `return_range` | `loiter` |
| `--transit-distance` | loiter | km | 10 |
| `--station-time` | loiter | minutes | 60 |
| `--distance` | range modes | km | 60 / 30 |
| `--payload` | all | kg | 4.0 |
| `--parts` | all | directory | `./parts` |

Every option has a default, so bare `python main.py` produces a card.

## Tests and lint

```bash
python -m pytest -q
ruff check .
```

## Build-time tools

`tools/` runs on a development machine and never ships. It may import anything
convenient; `aerosizer` may not, and
[tests/test_separation.py](tests/test_separation.py) enforces the boundary by
parsing every module in the package.

```bash
python -m tools.generate_parts   # regenerate the aerodynamic catalogue data
python -m tools.check_aero       # compare our drag polar against AeroSandbox
```

`generate_parts` writes the computed half of `parts/*.json` and the whole of
`parts/stability.json`. **Do not hand-edit those fields** — they are overwritten
on the next run.

## Using it as a library

The physics is a plain importable package with zero UI imports.

```python
from pathlib import Path

from aerosizer import Requirements, load_catalog, recommend, render_assembly_card
from aerosizer.mission import LoiterMission

catalog = load_catalog(Path("parts"))
requirements = Requirements(
    mission=LoiterMission(transit_distance=12_000.0, station_time=5400.0),
    payload_mass=4.0,
)

print(render_assembly_card(recommend(requirements, catalog)))
```

Three entry points, all pure functions over plain data:

- `analyze(configuration, atmosphere) -> Results` — the forward model.
  Evaluates one fully determined aircraft. It never solves for anything.
- `fly(configuration, profile, atmosphere) -> FlightLog` — marches a mission
  segment by segment, with mass falling as fuel burns.
- `recommend(requirements, catalog) -> Recommendation` — the product.
  Enumerates, sizes fuel, trims the tail, ranks, and returns the chosen
  configuration with its runner-up.

Every iterative solve lives in `recommend` — fuel mass for a stated mission,
tail extension for a target static margin — expressed as repeated calls to the
forward model. That is what keeps `analyze` a pure evaluation.

`Results` describes what an aircraft is *capable of*; `FlightLog` describes what
it *did on one sortie*. The two are deliberately separate.

`build_assembly_card(recommendation) -> AssemblyCard` is the display edge. It
returns structured, display-ready data; `render_assembly_card` renders that to
text, and the kiosk renders the same structure to widgets. Interfaces hold
layout and event plumbing only — every decision about units, wording and
severity is made once, in `assembly_card.py`, where it can be tested.

## Conventions

- **SI throughout.** Metres, kilograms, seconds, newtons, radians. Conversion
  happens only at the edges: in `catalog.py` when data is read, and in
  `assembly_card.py` when a number is shown.
- **Parts are data.** Adding a wing means adding a JSON entry in `parts/`,
  never editing a module. Catalogue keys carry explicit unit suffixes
  (`span_m`, `mass_kg`) because JSON has no other way to declare units.
- **Stations** are measured in metres aft of the nose datum, positive aft.

## Adding a part

Add an entry to `parts/wings.json` or `parts/empennages.json`, then regenerate
the computed fields:

```bash
python -m tools.generate_parts
```

Hand-authored fields are mass, stations, span, chords, areas and the
excrescence drag allowance. Generated fields are clean drag area, Oswald
efficiency, maximum lift coefficient and the neutral point table.

The catalogue loader is deliberately strict — a malformed or incomplete part
fails loudly at load time rather than producing a plausible and wrong card in a
field.

## Build state

Built as a tracer bullet: a thin end-to-end slice first, then thickened one
pass at a time.

| Phase | Contents | Status |
|---|---|---|
| 1 | Schemas, catalogue, enumerate → rank → card, kiosk | done |
| 2 | Mass and balance, drag polar, speed envelope, missions, fuel sizing, tail trim | done |
| 3 | Flyability gate, achievable envelope, infeasibility fallback | next |
| 4 | Part-load fuel consumption, tabulated polars | |
| 5 | Offline packaging, verified on a Raspberry Pi | |

Results report `Fidelity.PRELIMINARY`: the formulae and the geometry are real,
but two things underneath them are not yet trustworthy.

**Fuel figures are optimistic, probably by a factor of two or more.** Specific
fuel consumption is modelled at the engine's best point, while cruise sits at
about an eighth of full power — where a small two-stroke is far thirstier than
its nameplate. Nothing on the card carries a reserve either; the mission fuel
figure is what the sortie burns and no more.

**There is no flyability gate.** The tool will recommend a combination that is
badly out of balance rather than excluding it. Every configuration in the
current catalogue is over-stable — 21% to 50% static margin against a 12%
target — and the tail extension cannot correct it, because extending the boom
only adds stability. That is a real finding about the catalogue geometry, not a
bug, and it is reported rather than hidden.

The excrescence drag allowances are hand-authored judgements and are currently
the largest guess in the drag model.
