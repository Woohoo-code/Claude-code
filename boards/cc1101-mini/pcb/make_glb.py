#!/usr/bin/env python3
"""Write ../cc1101-mini.glb, a box-model 3D preview of the routed board,
using pcba-builder's glTF writer and the real placement from fab/*-pos.csv.

Run from anywhere with the repo on the path:  python3 make_glb.py
(needs fab/cc1101_mini-pos.csv, produced by make_fab.sh).
"""

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))  # repo root, for pcba_builder

from pcba_builder.bom import BomLine, PartInstance  # noqa: E402
from pcba_builder.glb_export import export_glb  # noqa: E402
from pcba_builder.packages import Package  # noqa: E402

BOARD_W, BOARD_H = 18.5, 12.6

# footprint -> (body w, body h, height, color); w/h are at rotation 0
BODIES = {
    "Texas_RGP0020H_VQFN-20-1EP_4x4mm_P0.5mm_EP2.4x2.4mm": (4.0, 4.0, 0.9, (0.05, 0.05, 0.05)),
    "Crystal_SMD_3225-4Pin_3.2x2.5mm": (3.2, 2.5, 0.8, (0.75, 0.75, 0.78)),
    "C_0402_1005Metric": (1.0, 0.5, 0.5, (0.65, 0.55, 0.35)),
    "L_0402_1005Metric": (1.0, 0.5, 0.5, (0.25, 0.25, 0.3)),
    "R_0402_1005Metric": (1.0, 0.5, 0.35, (0.1, 0.1, 0.1)),
    "U.FL_Hirose_U.FL-R-SMT-1_Vertical": (2.6, 2.6, 1.25, (0.8, 0.75, 0.55)),
    "PinHeader_1x08_P1.27mm_Vertical": (1.1, 10.2, 3.0, (0.05, 0.05, 0.1)),
}


def main() -> int:
    resolved, positions = [], []
    for r in csv.DictReader(open(HERE / "fab" / "cc1101_mini-pos.csv")):
        w, h, z, color = BODIES[r["Package"]]
        if round(float(r["Rot"])) % 180 == 90:
            w, h = h, w
        x, y = float(r["PosX"]), BOARD_H - float(r["PosY"])
        if r["Ref"] == "J2":  # footprint origin is pin 1, body is centered on the row
            y += 3.5 * 1.27
        line = BomLine(r["Ref"], "1", r["Val"], "", "", r["Package"], "")
        resolved.append((PartInstance(r["Ref"], line), Package(r["Package"], "", w, h, z, [], color)))
        positions.append((x, y))
    out = export_glb(HERE.parent, "cc1101-mini", resolved, positions, BOARD_W, BOARD_H)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
