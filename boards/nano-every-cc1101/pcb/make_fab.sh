#!/usr/bin/env bash
# Regenerate the board and every fabrication output.
#   needs: KiCad 7 (pcbnew Python + kicad-cli), kicad-footprints, Java +
#          Freerouting 1.9 jar (FREEROUTING_JAR), xvfb-run, librsvg2-bin (renders)
#   ./make_fab.sh           -> fab/nano_every_cc1101-gerbers.zip (upload this),
#                              fab/bom-jlcpcb.csv, fab/cpl-jlcpcb.csv, ../bom.csv,
#                              ../netlist.md, drc_report.txt, ../img/*.png
set -euo pipefail
cd "$(dirname "$0")"
export KICAD7_FOOTPRINT_DIR="${KICAD7_FOOTPRINT_DIR:-/usr/share/kicad/footprints}"
PCB=nano_every_cc1101.kicad_pcb

/usr/bin/python3 gen_board.py
rm -rf fab/gerbers && mkdir -p fab/gerbers
/usr/bin/python3 fab_outputs.py
kicad-cli pcb export gerbers -o fab/gerbers/ --no-protel-ext --use-drill-file-origin \
  -l F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts "$PCB" >/dev/null
kicad-cli pcb export drill -o fab/gerbers/ --format excellon --excellon-separate-th \
  --drill-origin plot --generate-map --map-format gerberx2 "$PCB" >/dev/null
rm -f fab/nano_every_cc1101-gerbers.zip
(cd fab/gerbers && zip -q -r ../nano_every_cc1101-gerbers.zip .)

mkdir -p ../img
kicad-cli pcb export svg -o ../img/top.svg -l F.Cu,F.Silkscreen,Edge.Cuts \
  --page-size-mode 2 --exclude-drawing-sheet "$PCB" >/dev/null
kicad-cli pcb export svg -o ../img/bottom.svg -l B.Cu,B.Silkscreen,Edge.Cuts \
  --page-size-mode 2 --exclude-drawing-sheet --mirror "$PCB" >/dev/null
if command -v rsvg-convert >/dev/null; then
  for s in top bottom; do rsvg-convert -w 1400 -b white ../img/$s.svg -o ../img/$s.png; done
  rm -f ../img/top.svg ../img/bottom.svg
fi
grep -E "Found" drc_report.txt
echo "fab outputs in $(pwd)/fab"
rm -rf logs
