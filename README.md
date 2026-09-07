# pcba-builder

A small CLI that drives the [Claude Code](https://claude.com/claude-code)
CLI (`claude`) to turn a plain-language board description into a first-pass
PCBA (printed circuit board assembly) design package: a bill of materials,
a logical netlist, schematic block descriptions, PCB layout/manufacturing
notes, and assembly/bring-up instructions.

It does not draw a schematic or route a board — there's no KiCad/Altium
integration here. It generates the structured text artifacts (BOM, netlist,
design notes) an engineer would hand-enter into an EDA tool, and a DFM/DFA
review pass to catch inconsistencies before that happens.

## Requirements

- Python 3.9+
- The `claude` CLI installed and authenticated (`claude --version` should work)

## Install

```
pip install -e .
```

This installs a `pcba-builder` command. You can also run it directly with
`python -m pcba_builder.cli` from the repo root.

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

```
pcba-builder review boards/led-driver
```

Cross-checks the generated files against each other and against the spec
(e.g. every net references a RefDes that actually exists in the BOM),
flags DFM/DFA risks, and writes `review.md`.

Pass `--model <name>` on any command to forward it to `claude --model`.

## How it works

Each command shells out to `claude -p "<prompt>"` with
`--permission-mode acceptEdits` and tool access limited to
`Write Edit Read Glob Grep` (no Bash, no network) scoped to the project
directory, so Claude can only read/write files inside the PCBA project
it's working on.
