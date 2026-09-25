# nano-every-cc1101: Arduino Nano Every + 2x CC1101, every sub-GHz band

A 100 x 100 mm **2-layer** carrier board for an Arduino Nano Every with two
TI CC1101 radios, so every band the CC1101 supports (300-348, 387-464 and
779-928 MHz) is covered. It has a printed antenna for each band, tuned with
a full-wave openEMS model, plus an SMA jack and a wire-whip hole per radio.
The Gerbers are generated and pass KiCad DRC with 0 errors and 0 unconnected pads.

| Top | Bottom (viewed from below) |
|---|---|
| ![top](img/top.png) | ![bottom](img/bottom.png) |

## What's on it

| | |
|---|---|
| Board | 100 x 100 x 1.6 mm, 2 layers, FR4 |
| Radio A (U1) | CC1101, 315/433 MHz front end (433 fitted) |
| Radio B (U501) | CC1101, 868/915 MHz front end |
| Antennas | printed 433 MHz (top edge), 315 MHz (left edge, loaded), 868 MHz and 915 MHz (right edge); SMA J1/J2; wire holes H1/H2 |
| Host | Arduino Nano Every in sockets, USB at the board edge, every pin re-broken-out on J3/J4 |
| Glue | TXS0108E 5 V <-> 3.3 V level shifter, AP2112K 3.3 V LDO, power LED |

Simulated antenna performance (with the T-match fitted; full table in
[`antenna/results/summary.md`](antenna/results/summary.md), plot in
`antenna/results/match.png`):

ANTENNA_TABLE

## Choosing the antenna

Fit **one** selector per radio (0603 0 ohm or the listed value):

| Radio | 433 MHz PCB | 315 MHz PCB | 868 MHz PCB | 915 MHz PCB | SMA / wire |
|---|---|---|---|---|---|
| A | **R301** (default) | R311 + 315 MHz BOM | | | R403 |
| B | | | **R321** (default) | R331 | R406 |

Wire whip lengths (quarter wave, from H1/H2): 164 mm @ 433, 226 mm @ 315,
82 mm @ 868, 78 mm @ 915. See `assembly_instructions.md` for the 315 MHz
BOM swap.

## Pins (Nano Every)

SPI shared: D13 SCK, D11 MOSI, D12 MISO. Radio A: CSn D10, GDO0 D2, GDO2 D3.
Radio B: CSn D9, GDO0 D4, GDO2 on test pad TP1 (3.3 V).
With RadioLib, e.g. `CC1101 radioA = new Module(10, 2, RADIOLIB_NC, 3);`
and `CC1101 radioB = new Module(9, 4, RADIOLIB_NC);`.

## Ordering (print ready)

1. PCB: upload `pcb/fab/nano_every_cc1101-gerbers.zip`. 2 layers, 1.6 mm,
   100 x 100 mm, 1 oz. All standard rules (0.15 mm track/space, 0.25 mm
   minimum drill), no special options.
2. Assembly (optional): `pcb/fab/bom-jlcpcb.csv` + `pcb/fab/cpl-jlcpcb.csv`
   (fitted parts only; check the rotations in the preview).
3. By hand: Nano sockets (2x 1x15 female), optional J3/J4 headers and SMA jacks.

## Files

| Path | What |
|---|---|
| `pcb/nano_every_cc1101.kicad_pcb` / `.kicad_pro` | The routed KiCad 7 board |
| `pcb/gen_board.py` | Generates the whole board (placement, RF routing, antennas, autorouting, pours) |
| `pcb/fab_outputs.py`, `pcb/make_fab.sh` | DRC, netlist, BOMs, CPL, Gerbers, renders |
| `pcb/fab/` | Gerbers + drills (zip), JLCPCB BOM + CPL |
| `pcb/drc_report.txt` | KiCad DRC report |
| `antenna/` | Antenna geometry, openEMS model, match designer, results |
| `bom.csv`, `netlist.md` | Generated from the board |
| `schematic_blocks.md`, `design_notes.md`, `assembly_instructions.md` | Design docs, bring-up |

## Limits

- Designed and simulated, not yet built or measured. Check each antenna
  with a nanoVNA once built; the T-match pads and the 2 mm trim marks on
  each antenna's open end are there to retune.
- 315 MHz from a 100 mm board is electrically small: it works, but with
  noticeably less efficiency than the others. The SMA/whip option is better
  at 315 MHz.
- No `.kicad_sch` schematic; the netlist is generated from the board.
- Not certified. Radiated use must follow your region's rules.
