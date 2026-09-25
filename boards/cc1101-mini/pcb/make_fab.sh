#!/usr/bin/env bash
# Regenerate the board and all fabrication outputs (KiCad 7 kicad-cli).
#   ./make_fab.sh            -> fab/gerbers/*, fab/cc1101_mini-gerbers.zip,
#                               fab/cc1101_mini-pos.csv, fab/cc1101_mini-cpl-jlc.csv
set -euo pipefail
cd "$(dirname "$0")"
export KICAD7_FOOTPRINT_DIR="${KICAD7_FOOTPRINT_DIR:-/usr/share/kicad/footprints}"
PCB=cc1101_mini.kicad_pcb

/usr/bin/python3 gen_board.py
rm -rf fab && mkdir -p fab/gerbers
kicad-cli pcb export gerbers -o fab/gerbers/ --no-protel-ext --use-drill-file-origin \
  -l F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts "$PCB" >/dev/null
kicad-cli pcb export drill -o fab/gerbers/ --format excellon --excellon-separate-th \
  --drill-origin plot --generate-map --map-format gerberx2 "$PCB" >/dev/null
kicad-cli pcb export pos -o fab/cc1101_mini-pos.csv --format csv --units mm --side front \
  --use-drill-file-origin "$PCB" >/dev/null
(cd fab/gerbers && zip -q -r ../cc1101_mini-gerbers.zip .)

# JLCPCB-style CPL (Designator,Mid X,Mid Y,Layer,Rotation)
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open("fab/cc1101_mini-pos.csv")))
with open("fab/cc1101_mini-cpl-jlc.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in rows:
        w.writerow([r["Ref"], f'{float(r["PosX"]):.3f}mm', f'{float(r["PosY"]):.3f}mm',
                    "Top", f'{float(r["Rot"]):.0f}'])
PY
echo "fab outputs written to $(pwd)/fab"

# 3D box preview via pcba-builder's glTF writer
python3 make_glb.py

# Layer renders for the README
mkdir -p ../img
kicad-cli pcb export svg -o ../img/top.svg -l F.Cu,F.Silkscreen,F.Fab,Edge.Cuts \
  --page-size-mode 2 --exclude-drawing-sheet "$PCB" >/dev/null
kicad-cli pcb export svg -o ../img/bottom.svg -l B.Cu,B.Silkscreen,Edge.Cuts \
  --page-size-mode 2 --exclude-drawing-sheet --mirror "$PCB" >/dev/null
if command -v rsvg-convert >/dev/null; then
  for s in top bottom; do rsvg-convert -w 1400 -b white ../img/$s.svg -o ../img/$s.png; done
  rm -f ../img/top.svg ../img/bottom.svg
fi
