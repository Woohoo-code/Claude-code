"""CLI entry point for pcba-builder.

Wraps the `claude` CLI (Claude Code) to turn a plain-language board spec
into a PCBA design package: bill of materials, netlist, layout notes, and
assembly instructions.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SPEC_TEMPLATE = """\
# Board spec

## Function
<!-- What does this board do? e.g. "USB-C powered RGB LED strip controller" -->

## Inputs / outputs
<!-- Connectors, signals, voltages, e.g. "USB-C (5V in), 3x JST-PH 3-pin LED outputs" -->

## Power
<!-- Supply voltage(s), current budget, battery vs. mains, regulation needs -->

## Key components
<!-- MCU/IC choices if you have preferences, sensors, connectors. Leave blank to let
     Claude propose parts. -->

## Constraints
<!-- Board outline size, mounting holes, layer count, cost target, certifications -->

## Notes
<!-- Anything else: enclosure fit, EMI concerns, planned production quantity -->
"""

BUILD_PROMPT = """\
You are acting as a PCBA (printed circuit board assembly) design assistant.
Read the board spec in `spec.md` in the current directory and produce a
complete first-pass design package as separate files in this same
directory. Do not ask clarifying questions — state assumptions inline in
the files instead. Create exactly these files:

1. `bom.csv` - Bill of materials. Columns: RefDes,Qty,Description,
   Manufacturer,MPN,Package,Notes. Group passives by value. Every part
   must have a real or realistic manufacturer part number and package
   (e.g. 0402, SOT-23-5, QFN-32).

2. `netlist.md` - A human-and-EDA-readable logical netlist. For each net,
   list the net name and every RefDes.pin connected to it. Group nets by
   function (power, ground, signal buses, individual GPIO). This is not a
   KiCad binary netlist - it's a structured markdown table an engineer can
   hand-enter into any EDA tool.

3. `schematic_blocks.md` - A description of the schematic organized by
   functional block (power supply, MCU/core, each connector, protection
   circuitry, etc.). For each block: purpose, key component values
   (resistor/cap values with tolerances, inductor specs), and a short
   ASCII sketch of the topology where it helps (e.g. a buck converter
   feedback divider).

4. `design_notes.md` - PCB layout and manufacturing guidance: recommended
   layer count and stackup, trace widths/clearances for the power nets
   (with current-carrying calculations), thermal considerations, EMI/ESD
   mitigation, decoupling capacitor placement rules, and any DFM
   (design-for-manufacturability) constraints (min trace/space, via size,
   solder mask, panelization) relevant to the stated production quantity.

5. `assembly_instructions.md` - PCBA assembly and bring-up guidance:
   placement order (paste, SMT reflow, THT wave/hand solder), a suggested
   reflow profile if leaded/lead-free is not specified assume lead-free
   SAC305, and a bring-up test checklist (power-on sequence, voltage rail
   checks, continuity/short checks before first power-on).

Ground every value in the spec's stated requirements. Where you must
choose a part the spec left open, pick a specific, commonly-stocked part
(prefer parts available from Digi-Key/Mouser/LCSC) and note the choice was
yours in `design_notes.md` under a "Design decisions" heading.
"""

REVIEW_PROMPT = """\
You are performing a design-for-manufacturability and design-for-assembly
(DFM/DFA) review of the PCBA package in the current directory
(`spec.md`, `bom.csv`, `netlist.md`, `schematic_blocks.md`,
`design_notes.md`, `assembly_instructions.md`). Cross-check the files
against each other for consistency (e.g. every net in `netlist.md`
references RefDes that exist in `bom.csv`; power budget in `design_notes.md`
matches the supply described in `spec.md`).

Write findings to `review.md`, organized as:

- Consistency issues (mismatches between files)
- DFM/DFA risks (manufacturability, assembly, testability concerns)
- Suggested fixes (concrete, actionable)

Do not modify the other files - `review.md` only.
"""


def scaffold(project_dir: Path) -> None:
    if project_dir.exists() and any(project_dir.iterdir()):
        print(f"error: {project_dir} already exists and is not empty", file=sys.stderr)
        raise SystemExit(1)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "spec.md").write_text(SPEC_TEMPLATE)
    print(f"Created {project_dir}/spec.md - fill it in, then run:")
    print(f"  pcba-builder build {project_dir}")


def require_claude_cli() -> str:
    claude_path = shutil.which("claude")
    if not claude_path:
        print(
            "error: the `claude` CLI was not found on PATH. Install Claude Code "
            "(https://claude.com/claude-code) and make sure `claude` is available.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return claude_path


def run_claude(project_dir: Path, prompt: str, model: str | None) -> int:
    require_claude_cli()
    cmd = [
        "claude",
        "-p",
        prompt,
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Write Edit Read Glob Grep",
        "--add-dir",
        str(project_dir),
    ]
    if model:
        cmd += ["--model", model]
    result = subprocess.run(cmd, cwd=project_dir)
    return result.returncode


def build(project_dir: Path, model: str | None) -> None:
    spec_path = project_dir / "spec.md"
    if not spec_path.exists():
        print(
            f"error: {spec_path} not found. Run `pcba-builder new {project_dir}` first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    rc = run_claude(project_dir, BUILD_PROMPT, model)
    raise SystemExit(rc)


def review(project_dir: Path, model: str | None) -> None:
    required = ["spec.md", "bom.csv", "netlist.md", "design_notes.md"]
    missing = [f for f in required if not (project_dir / f).exists()]
    if missing:
        print(
            f"error: missing {', '.join(missing)} in {project_dir}. "
            f"Run `pcba-builder build {project_dir}` first.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    rc = run_claude(project_dir, REVIEW_PROMPT, model)
    raise SystemExit(rc)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pcba-builder",
        description="Use the Claude Code CLI to design a PCBA from a plain-language spec.",
    )
    parser.add_argument("--model", help="model to pass through to `claude --model`")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="scaffold a new PCBA project with a spec template")
    p_new.add_argument("project_dir", type=Path)

    p_build = sub.add_parser(
        "build", help="generate BOM, netlist, layout notes, and assembly docs from spec.md"
    )
    p_build.add_argument("project_dir", type=Path)

    p_review = sub.add_parser(
        "review", help="run a DFM/DFA consistency review over an existing project"
    )
    p_review.add_argument("project_dir", type=Path)

    args = parser.parse_args(argv)

    if args.command == "new":
        scaffold(args.project_dir)
    elif args.command == "build":
        build(args.project_dir, args.model)
    elif args.command == "review":
        review(args.project_dir, args.model)


if __name__ == "__main__":
    main()
