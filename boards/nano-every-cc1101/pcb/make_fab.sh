#!/usr/bin/env bash
# Regenerate the board and every fabrication output.
#   needs: KiCad 7 (pcbnew Python + kicad-cli), kicad-footprints, Java +
#          Freerouting 1.9 jar (FREEROUTING_JAR), xvfb-run, librsvg2-bin (renders)
#   ./make_fab.sh           -> fab/nano_every_cc1101-gerbers.zip (upload this to the fab),
#                              fab/bom-jlcpcb.csv, fab/cpl-jlcpcb.csv, ../bom.csv,
#                              ../netlist.md, drc_report.txt, ../img/*.png
set -euo pipefail
cd "$(dirname "$0")"
export KICAD7_FOOTPRINT_DIR="${KICAD7_FOOTPRINT_DIR:-/usr/share/kicad/footprints}"
PCB=nano_every_cc1101.kicad_pcb

/usr/bin/python3 gen_board.py
rm -rf fab/gerbers && mkdir -p fab/gerbers
/usr/bin/python3 fab_outputs.py
# Fab layers only, with the Protel extensions fabs key on (.GTL/.GBL/.GTS/
# .GBS/.GTP/.GTO/.GBO/.GM1 + .DRL). No drill maps (they are drawings that
# upload tools misread as layers), no empty drill files, and no aperture
# macros (web viewers such as Gerblook/tracespace mis-draw KiCad's RoundRect
# macro; pads are written as plain flashes/regions instead), and plain RS-274X
# (no X2 / netlist attributes) so every viewer and fab reads it the same way.
kicad-cli pcb export gerbers -o fab/gerbers/ --use-drill-file-origin --subtract-soldermask \
  --disable-aperture-macros --no-x2 --no-netlist \
  -l F.Cu,B.Cu,F.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts "$PCB" >/dev/null
kicad-cli pcb export drill -o fab/gerbers/ --format excellon --excellon-separate-th \
  --excellon-units mm --excellon-zeros-format decimal --drill-origin plot "$PCB" >/dev/null
for f in fab/gerbers/*.drl; do
  grep -qE '^T[0-9]+C' "$f" || rm -f "$f"        # drop a drill file with no tools
done
rm -f fab/nano_every_cc1101-gerbers.zip
rm -f fab/gerbers/*.gbrjob                       # JSON, not a layer; viewers choke on it
(cd fab/gerbers && zip -q -j ../nano_every_cc1101-gerbers.zip ./*)
rm -f fab/nano_every_cc1101-fab-package.zip
(cd fab && zip -q -j nano_every_cc1101-fab-package.zip nano_every_cc1101-gerbers.zip \
  bom-no-nano.csv bom-jlcpcb.csv cpl-jlcpcb.csv)

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
