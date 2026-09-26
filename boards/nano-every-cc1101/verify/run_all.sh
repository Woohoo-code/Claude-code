#!/bin/bash
# Re-run every check on the current board. KiCad's Python extracts the board,
# a Python with numpy + scipy runs the analyses (PY=...).
set -e
cd "$(dirname "$0")"
KPY=${KPY:-/usr/bin/python3}
PY=${PY:-python3}
PCB=../pcb/nano_every_cc1101.kicad_pcb
T=$(mktemp -d)
echo "== DRC";                        grep -E "Found" ../pcb/drc_report.txt
echo "== pins vs vendor pin names";   $KPY extract_fp.py $PCB $T/fp.json >/dev/null; $PY schcheck.py $T/fp.json
echo "== CPL vs JLCPCB footprints";   $PY cplfit.py $T/fp.json ../pcb/fab/bom-jlcpcb.csv 45 $T/cpl_fit.csv ../pcb/fab/cpl-jlcpcb.csv | tail -1
echo "== line impedance (2-D field solver)"; $PY fieldsolve.py 1.2 0.4
echo "== antenna feed networks";      $KPY extract_rf.py $PCB $T/rf.json >/dev/null; $PY rfnet.py $T/rf.json
echo "== CC1101 harmonic filters";    $PY lpf.py
echo "== Gerber DFM (the files the fab receives)"; $PY gerber_dfm.py ../pcb/fab/nano_every_cc1101-gerbers.zip
echo "== routing";                    $KPY route_metrics.py $PCB; $KPY detour.py $PCB 0 | tail -1
echo "== power";                      $PY power.py
rm -rf $T
