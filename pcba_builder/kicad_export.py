"""Generate KiCad footprint (.kicad_mod) and PCB (.kicad_pcb) files.

Placement is an auto-arranged grid, not a routed or optimized layout - it's
a valid, loadable starting point (real footprints, real pad geometry, a
board outline) for an engineer to place and route in KiCad.
"""

from __future__ import annotations

import math
from pathlib import Path

from .bom import PartInstance
from .packages import Package, build_package

_HEADER_FOOTPRINT = """(footprint "PCBA_BUILDER:{name}" (version 20221018) (generator pcba-builder)
  (layer "F.Cu")
  (attr {attr})
  (fp_text reference "{ref}" (at 0 {ref_y}) (layer "F.SilkS")
    (effects (font (size 1 1) (thickness 0.15))))
  (fp_text value "{value}" (at 0 {val_y}) (layer "F.Fab")
    (effects (font (size 1 1) (thickness 0.15))))
{pads}
)
"""

_INSTANCE_FOOTPRINT = """  (footprint "PCBA_BUILDER:{name}" (layer "F.Cu") (at {x} {y})
    (attr {attr})
    (fp_text reference "{ref}" (at 0 {ref_y}) (layer "F.SilkS")
      (effects (font (size 1 1) (thickness 0.15))))
    (fp_text value "{value}" (at 0 {val_y}) (layer "F.Fab")
      (effects (font (size 1 1) (thickness 0.15))))
{pads}
  )
"""


def _pad_sexpr(pin, indent: str) -> str:
    if pin.shape == "circle" and pin.drill_mm:
        return (
            f'{indent}(pad "{pin.number}" thru_hole circle (at {pin.x_mm} {pin.y_mm}) '
            f"(size {pin.pad_w_mm} {pin.pad_h_mm}) (drill {pin.drill_mm}) "
            f'(layers "*.Cu" "*.Mask"))'
        )
    return (
        f'{indent}(pad "{pin.number}" smd rect (at {pin.x_mm} {pin.y_mm}) '
        f"(size {pin.pad_w_mm} {pin.pad_h_mm}) "
        f'(layers "F.Cu" "F.Paste" "F.Mask"))'
    )


def render_footprint_lib(pkg: Package) -> str:
    attr = "through_hole" if pkg.kind in ("dip", "to220", "to92", "header") else "smd"
    pads = "\n".join(_pad_sexpr(p, "  ") for p in pkg.pins)
    ref_y = -pkg.body_h_mm / 2 - 1.2
    val_y = pkg.body_h_mm / 2 + 1.2
    return _HEADER_FOOTPRINT.format(
        name=pkg.name, attr=attr, ref="REF**", ref_y=ref_y, value=pkg.name,
        val_y=val_y, pads=pads,
    )


def render_footprint_instance(pkg: Package, refdes: str, value: str, x: float, y: float) -> str:
    attr = "through_hole" if pkg.kind in ("dip", "to220", "to92", "header") else "smd"
    pads = "\n".join(_pad_sexpr(p, "    ") for p in pkg.pins)
    ref_y = -pkg.body_h_mm / 2 - 1.2
    val_y = pkg.body_h_mm / 2 + 1.2
    value = value.replace('"', "'")[:40] or pkg.name
    return _INSTANCE_FOOTPRINT.format(
        name=pkg.name, attr=attr, ref=refdes, ref_y=ref_y, value=value,
        val_y=val_y, pads=pads, x=round(x, 3), y=round(y, 3),
    )


def _grid_layout(items: list[tuple[PartInstance, Package]], margin: float = 5.0):
    """Return (positions, board_w, board_h). positions[i] = (x, y) board-space."""
    if not items:
        return [], 40.0, 30.0
    cell = max(max(pkg.body_w_mm, pkg.body_h_mm) for _, pkg in items) + 3.0
    n = len(items)
    cols = max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)
    board_w = cols * cell + margin * 2
    board_h = rows * cell + margin * 2
    positions = []
    for i in range(n):
        row, col = divmod(i, cols)
        x = margin + cell / 2 + col * cell
        y = margin + cell / 2 + row * cell
        positions.append((x, y))
    return positions, board_w, board_h


def export_kicad(project_dir: Path, project_name: str) -> dict:
    """Read bom.csv, write kicad/footprints/*.kicad_mod, kicad/<project>.kicad_pcb,
    and pinouts.md. Returns a summary dict with recognized/unrecognized counts."""
    from .bom import load_bom

    bom_path = project_dir / "bom.csv"
    instances = load_bom(bom_path)

    resolved: list[tuple[PartInstance, Package]] = []
    unrecognized: list[str] = []
    seen_packages: dict[str, Package] = {}

    for inst in instances:
        pkg = build_package(inst.line.package)
        if pkg is None:
            unrecognized.append(f"{inst.refdes} ({inst.line.package or 'no package given'})")
            continue
        resolved.append((inst, pkg))
        seen_packages.setdefault(pkg.name, pkg)

    kicad_dir = project_dir / "kicad"
    fp_dir = kicad_dir / "footprints"
    fp_dir.mkdir(parents=True, exist_ok=True)
    for pkg in seen_packages.values():
        (fp_dir / f"{pkg.name}.kicad_mod").write_text(render_footprint_lib(pkg))

    positions, board_w, board_h = _grid_layout(resolved)

    footprint_blocks = []
    pinout_rows = []
    for (inst, pkg), (x, y) in zip(resolved, positions):
        footprint_blocks.append(
            render_footprint_instance(pkg, inst.refdes, inst.line.mpn or inst.line.description, x, y)
        )
        for pin in pkg.pins:
            pinout_rows.append(
                f"| {inst.refdes} | {pkg.name} | {pin.number} | "
                f"{round(x + pin.x_mm, 3)} | {round(y + pin.y_mm, 3)} | "
                f"{pin.pad_w_mm}x{pin.pad_h_mm} | {'yes' if pin.is_pin1 else ''} |"
            )

    pcb = "\n".join(
        [
            "(kicad_pcb (version 20221018) (generator pcba-builder)",
            "  (general",
            "    (thickness 1.6)",
            "  )",
            '  (paper "A4")',
            "  (layers",
            '    (0 "F.Cu" signal)',
            '    (31 "B.Cu" signal)',
            '    (34 "B.Mask" user)',
            '    (35 "F.Mask" user)',
            '    (36 "B.SilkS" user)',
            '    (37 "F.SilkS" user)',
            '    (44 "Edge.Cuts" user)',
            "  )",
            "  (setup",
            "    (pad_to_mask_clearance 0)",
            "  )",
            '  (net 0 "")',
            f"  (gr_rect (start 0 0) (end {board_w} {board_h}) "
            '(layer "Edge.Cuts") (width 0.15))',
            *footprint_blocks,
            ")",
            "",
        ]
    )
    pcb_path = kicad_dir / f"{project_name}.kicad_pcb"
    pcb_path.write_text(pcb)

    pinout_md = ["# Pin positions (from package shape/size)", ""]
    if pinout_rows:
        pinout_md.append("| RefDes | Package | Pin | X (mm) | Y (mm) | Pad size (mm) | Pin 1 |")
        pinout_md.append("|---|---|---|---|---|---|---|")
        pinout_md.extend(pinout_rows)
    else:
        pinout_md.append("No recognized packages found in bom.csv.")
    if unrecognized:
        pinout_md.append("")
        pinout_md.append("## Unrecognized packages (no footprint generated)")
        pinout_md.extend(f"- {u}" for u in unrecognized)
        pinout_md.append("")
        pinout_md.append(
            f"Known package names: {', '.join(sorted(seen_packages.keys()) or ['(none matched)'])}"
            " - see `pcba_builder/packages.py` for the full recognized list."
        )
    (project_dir / "pinouts.md").write_text("\n".join(pinout_md) + "\n")

    return {
        "recognized": len(resolved),
        "unrecognized": len(unrecognized),
        "board_w_mm": board_w,
        "board_h_mm": board_h,
        "positions": positions,
        "resolved": resolved,
        "pcb_path": pcb_path,
    }
