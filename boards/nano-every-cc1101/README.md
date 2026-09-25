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

| Antenna | Arm (mm) | Tap / tail (mm) | Z at f0 (ohm) | S11 unmatched | T-match S1 / shunt / S2 | S11 matched | -10 dB band (MHz) | match loss |
|---|---|---|---|---|---|---|---|---|
| 433 MHz | 153 | 3 / 52 | 73.8-13.9j | -13.1 dB | 16pF / 56nH / 0R | -15.9 dB | 431-437 | 0.1 dB |
| 315 MHz | 211 | 4 / 50 | 27.7+55.2j | -4.1 dB | 0R / 27nH / 6.8pF | -18.7 dB | 313-317 | 0.1 dB |
| 868 MHz | 60 | 4 / 10 | 26.6+53.8j | -4.1 dB | 0R / 3.6pF / 6.2pF | -31.0 dB | 847-883 | 0.0 dB |
| 915 MHz | 58 | 4 / 8 | 36.4+90.1j | -2.7 dB | 0R / 2.4pF / 2.7pF | -26.1 dB | 899-1041 | 0.0 dB |

Match loss = power lost in the T-match parts (0603, inductor Q 40, capacitor Q 300).
315 MHz additionally loses power in its arm's 47 nH loading coil (L402, Q 40): coil + match pass about 40 % (-4 dB) of the power on to the antenna (`choose_load.py`), so expect noticeably less range at 315 MHz than on the other bands.
ISM bands covered by the -10 dB bands: 433.05-434.79 (433), 314-316 (315), 863-870 (868), 902-928 (915).

## Choosing the antenna

Fit **one** selector per radio (0603; R301 is a 16 pF capacitor, the others 0 ohm):

| Radio | 433 MHz PCB | 315 MHz PCB | 868 MHz PCB | 915 MHz PCB | SMA / wire |
|---|---|---|---|---|---|
| A | **R301** 16 pF (default) | R311 0R + 315 MHz BOM | | | R403 0R |
| B | | | **R321** 0R (default) | R331 0R | R406 0R |

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
