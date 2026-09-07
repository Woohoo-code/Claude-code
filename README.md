# pcba-builder

A CLI that drives the [Claude Code](https://claude.com/claude-code) CLI
(`claude`) to turn a plain-language board description into a first-pass
PCBA (printed circuit board assembly) design package: a bill of materials,
a logical netlist, schematic block descriptions, PCB layout/manufacturing
notes, and assembly/bring-up instructions - plus, generated locally and
offline from that BOM:

- **KiCad export** - real `.kicad_mod` footprints and a placed (unrouted)
  `.kicad_pcb`, with every pin positioned and numbered from its package's
  physical shape and size (JEDEC/IPC-style: pin 1 marked, numbering
  counterclockwise around the body) - see `pinouts.md`.
- **GLB export** - a `.glb` 3D preview of the assembled board (board slab
  + one box per part, sized and placed to match the KiCad layout) you can
  open in any glTF viewer.
- **Online model search** - `pcba-builder models` uses `claude -p` with
  web search to look up a datasheet and, where one exists, a direct
  downloadable 3D/footprint file (STEP/IGES/WRL/GLB) for each part in the
  BOM, and fetches any direct links it finds.
- **Standalone executable** - `scripts/build_exe.sh` / `build_exe.bat`
  package the whole tool with PyInstaller into a single `pcba-builder`
  (or `pcba-builder.exe` on Windows) binary - no Python install needed to
  run it.

It does not draw a schematic or auto-route a board. `export-kicad`
produces a *placed but unrouted* starting point (no ratsnest - the
underlying netlist connectivity from `netlist.md` isn't wired into the
`.kicad_pcb` yet), and `models`/pin-labeling are geometry- and
search-driven, not a guarantee that a given part's silicon pinout matches
the physical positions generated. Always check a generated design against
the real datasheet before fabricating.

## Requirements

- Python 3.9+ (only to run from source - the packaged executable needs nothing)
- The `claude` CLI installed and authenticated (`claude --version` should work),
  for `build`, `review`, and `models`
- Internet access (through your normal `claude` CLI setup) for `models`

## Install (from source)

```
pip install -e .
```

This installs a `pcba-builder` command. You can also run it directly with
`python -m pcba_builder.cli` from the repo root.

## Build a standalone executable

```
./scripts/build_exe.sh      # Linux/macOS -> dist/pcba-builder
scripts\build_exe.bat       # Windows     -> dist\pcba-builder.exe
```

PyInstaller doesn't cross-compile, so build on the OS you want to run on.
The resulting binary bundles Python and every dependency; it still shells
out to your system's `claude` CLI for `build`/`review`/`models`, so that
still needs to be installed and authenticated separately.

## Usage

```
pcba-builder new boards/led-driver
```

Fills in `boards/led-driver/spec.md` with a template. Edit it to describe
the board: function, connectors/IO, power budget, any parts you already
want to use, and constraints (board size, layer count, cost/quantity).

```
pcba-builder build boards/led-driver
```

Runs `claude -p` against that spec and writes into `boards/led-driver/`:

- `bom.csv` — bill of materials with manufacturer part numbers
- `netlist.md` — nets and connected RefDes.pin lists
- `schematic_blocks.md` — schematic organized by functional block
- `design_notes.md` — layout, stackup, trace-width, EMI, and DFM guidance
- `assembly_instructions.md` — placement order, reflow profile, bring-up checklist

Then, automatically and entirely offline (no `claude` call, deterministic
from `bom.csv`):

- `pinouts.md` — every recognized part's pins, numbered and positioned
  from its package geometry
- `kicad/footprints/*.kicad_mod` and `kicad/<project>.kicad_pcb`
- `<project>.glb` — a 3D preview of the populated board

Re-run just those two exports later (e.g. after hand-editing `bom.csv`)
with `pcba-builder export-kicad boards/led-driver` (regenerates both the
KiCad files and the GLB) or `pcba-builder export-glb boards/led-driver`.

Recognized packages (see `pcba_builder/packages.py` for the authoritative
list): chip passives (0201-2512), SOT-23-3/5/6, SOIC-8/14/16,
TSSOP-8/14/16/20, QFN-16/20/24/32, DIP-8/14/16, TO-220, TO-92, 2.54mm
headers (`HDR-1xN`), and JST-PH connectors. A part whose `Package` field
in `bom.csv` doesn't match gets listed under "Unrecognized packages" in
`pinouts.md` instead of silently dropped.

```
pcba-builder models boards/led-driver
```

Uses `claude -p` with web search to look up each distinct MPN in the BOM
and writes `models/manifest.csv` (MPN, datasheet URL, model URL/format,
source, license note). Any manifest row with a direct link to a
`.step`/`.stp`/`.iges`/`.igs`/`.wrl`/`.glb`/`.gltf` file is then fetched
(size-capped, up to 25 files) into `models/`; everything else is left as
a link in the manifest for you to fetch by hand (e.g. it's behind a
SnapEDA/Ultra Librarian login). Logged to `models/download_log.md`.

```
pcba-builder review boards/led-driver
```

Cross-checks the generated files against each other and against the spec
(e.g. every net references a RefDes that actually exists in the BOM),
flags DFM/DFA risks, and writes `review.md`.

Pass `--model <name>` on any command that calls `claude` to forward it to
`claude --model`.

## How it works

`build`, `review`, and `models` shell out to `claude -p "<prompt>"` with
`--permission-mode acceptEdits` and tool access limited to what each step
needs (`Write Edit Read Glob Grep` for design generation; add
`WebSearch WebFetch` for `models`) — no Bash, scoped to the project
directory, so Claude can only read/write files inside the PCBA project
it's working on and (for `models`) search/fetch web pages.

`export-kicad` and `export-glb` don't call Claude at all: they parse
`bom.csv`, look up each part's package in a small geometry database
(`pcba_builder/packages.py`), lay parts out on a grid, and write the
KiCad and glTF files directly.
