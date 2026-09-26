#!/bin/bash
# Re-run every check on the current board. KiCad's Python extracts the board,
# a Python with numpy + scipy runs the analyses (PY=...).
set -e
# ONLINE=1 also checks every BOM line against the live LCSC record and stock;
# FULLWAVE=1 adds the 3-D openEMS simulation of the 50 ohm line.
cd "$(dirname "$0")"
KPY=${KPY:-/usr/bin/python3}
PY=${PY:-python3}
PCB=../pcb/nano_every_cc1101.kicad_pcb
T=$(mktemp -d)
echo "== DRC";                        grep -E "Found" ../pcb/drc_report.txt
echo "== pins vs vendor pin names";   $KPY extract_fp.py $PCB $T/fp.json >/dev/null; $PY schcheck.py $T/fp.json
echo "== firmware pins traced through the board"; $PY fwtrace.py $T/fp.json ../firmware/dual_cc1101/dual_cc1101.ino | tail -1
echo "== CPL vs JLCPCB footprints";   $PY cplfit.py $T/fp.json ../pcb/fab/bom-jlcpcb.csv 45 $T/cpl_fit.csv ../pcb/fab/cpl-jlcpcb.csv | tail -1
echo "== line impedance (2-D field solver)"; $PY fieldsolve.py 1.2 0.4
if [ -n "${FULLWAVE:-}" ]; then                   # ~3 min: 3-D openEMS FDTD of the 50 ohm line
  echo "== line impedance (3-D full-wave, openEMS)"; $PY fullwave_cpwg.py 2>/dev/null | tail -5
fi
echo "== antenna feed networks";      $KPY extract_rf.py $PCB $T/rf.json >/dev/null; $PY rfnet.py $T/rf.json
echo "== CC1101 harmonic filters";    $PY lpf.py
echo "== Gerber DFM (the files the fab receives)"; $PY gerber_dfm.py ../pcb/fab/nano_every_cc1101-gerbers.zip
echo "== Gerber netlist + DFM (fab files only: shorts/opens, clearances, rings, mask, paste)"
$KPY extract_pads.py $PCB $T/pads.json >/dev/null; $PY -W ignore gerber_nets.py ../pcb/fab/nano_every_cc1101-gerbers.zip $T/pads.json
echo "== SMD spacing vs JLCPCB's table"; $KPY extract_bodies.py $PCB $T/bodies.json; $PY spacing.py $T/bodies.json ../pcb/fab/cpl-jlcpcb.csv
echo "== routing";                    $KPY route_metrics.py $PCB; $KPY detour.py $PCB 0 | tail -1
echo "== power";                      $PY power.py
if [ -n "${ONLINE:-}" ]; then                     # live JLCPCB/LCSC data
  echo "== parts vs LCSC records";   $PY partcheck.py ../pcb/fab/bom-jlcpcb.csv $T/parts.json
  echo "== stock";                   $PY stock.py ../pcb/fab/bom-jlcpcb.csv 5
fi
rm -rf $T
