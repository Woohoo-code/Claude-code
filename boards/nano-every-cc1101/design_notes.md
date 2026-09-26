# Design notes

## Why two radios

The CC1101 covers 300-348, 387-464 and 779-928 MHz, but its RF pins need a
band-specific balun + filter, and TI's 315/433 MHz and 868/915 MHz networks
are different topologies (SWRS061I Fig. 10 vs Fig. 11), not just different
values. One CC1101 can therefore only be good in one band group. This board
carries two:

| Radio | Chip | Front end | Bands | Antennas |
|---|---|---|---|---|
| A | U1 | Fig. 10 (L/C balun + LC low-pass), 433 MHz values fitted | 387-464 MHz; 300-348 MHz after the 315 MHz BOM swap | coils AE1 433, AE2 315; SMA J1 |
| B | U501 | Fig. 11 (wire-wound balun + LC low-pass) | 779-928 MHz | coils AE3 868, AE4 915; SMA J2 |

Both share SPI (SCK/MOSI/MISO; the CC1101's SO pin is high-impedance while
CSn is high) and have their own CSn and GDO0. Radio A also has GDO2 on the
Nano; radio B's GDO2 goes to test pad TP1, because the one TXS0108E has 8
channels and that is the ninth signal.

## Board

| Item | Value |
|---|---|
| Size | 70 x 45 mm (coil antennas instead of printed ones) |
| Layers | **2**: F.Cu parts + routing + ground pour, B.Cu ground plane + a few routes |
| Thickness | 1.6 mm FR4 |
| Min track / space | 0.15 / 0.15 mm (0.15 mm only inside the two CC1101 clusters) |
| Vias | 0.6 / 0.3 mm; 0.5 / 0.25 mm inside the CC1101 clusters |
| Ground | solid pour on both layers except the coil strips, 153 ground vias |
| Coil strips | copper-free, 7 x 15 mm at the top-right and bottom-right corners |

## RF layout

- Each CC1101 cluster is the routed layout from `boards/cc1101-mini`: QFN
  with 5 tented vias in the exposed pad, a 100 nF cap and via on every
  supply pin, and the crystal on its own short traces. The mini used a
  4-layer VCC plane; here a short B.Cu ring links the chip's AVDD/DGUARD
  vias instead, and 3.3 V arrives on top-layer traces.
- Radio B keeps the same core and replaces the balun with TI's 868/915 MHz
  network (L131/L121 series, C121 across, C131 + L132, L122 + C124 + C122,
  then L123-C123-L124-C125).
- 50 ohm lines are 1.2 mm grounded coplanar waveguide with 0.2 mm gaps over
  the unbroken B.Cu ground (49.7-51.4 ohm from a 2-D field solve of the real
  cross-section, `verify/fieldsolve.py`), with stitching vias along both
  sides wherever they fit. Each coil branch is 50 ohm from the bus to the
  coil.
- Each radio has a short vertical 50 ohm bus; every antenna branch starts
  with its selector right on the bus, so an unselected branch is a stub of
  only a few mm (negligible below 1 GHz).
- The B.Cu ground plane is kept free of routing under both RF paths, all
  match networks and the SMA lines (Freerouting keep-outs), and two ground
  corridors per radio are kept open so the CC1101 exposed pad and its
  decoupling grounds always reach the main pours.

## Antennas

Four helical spring ("coil") antennas, one per band, BAT WIRELESS
BWxxxSNX (315/433/868/915 MHz, LCSC C496553-C496556). They stand up from
the right-hand board edge in two copper-free strips, 8.7 mm apart, with a
ground-via fence along the strip edge; the board's ground pour is their
counterpoise. They are pre-tuned by the maker, so the default T-match is
0 ohm / empty / 0 ohm. They are not simulated on this board: the earlier
printed-antenna study in `antenna/` (openEMS) does not apply to them.
All four are fitted, so the unselected coil next to the active one acts as
a parasitic element; expect a small detuning (largest for 868 vs 915) and
trim the T-match with a nanoVNA if needed.

## Level shifting and power

- The Nano Every is 5 V logic; the CC1101 is 3.6 V max. A TXS0108E
  (auto-direction, 3.3 V A side, 5 V B side) sits between them.
- XC6206P332MR 3.3 V LDO (JLCPCB basic part) from the Nano's 5 V pin:
  200 mA available, two radios in TX draw ~60 mA.

## Autorouting

The TXS0108E sits rotated 270 deg with its channels in the Nano's pin order:
the shortest of 24 fully routed placements (rotation x channel order x
position), 622 mm autorouted copper and 9 signal vias, 1.17x the
straight-line minimum overall (`verify/VERIFICATION.md`).

Freerouting only routes the non-RF signals (SPI, CSn/GDO, 3.3 V/5 V, LED).
Everything RF, both CC1101 clusters, every match network, antenna and
power stub is placed and routed by `pcb/gen_board.py` itself. Ground is
never routed: every ground pad has its own via into both pours.

## DRC

`pcb/drc_report.txt`: **0 violations, 0 unconnected pads**. Two project
settings make that possible without hiding real problems:
- `pcb/nano_every_cc1101.kicad_dru` lets the CC1101 decoupling / bias
  parts' courtyards touch the QFN's courtyard margin (their pads and bodies
  clear the package, as in TI's reference layouts). C41/C51 were moved
  0.15 mm out so the DCOUPL cap's body clears the package by 0.1 mm.
- the library-sync check is off: `gen_board.py` clips footprint silkscreen
  strokes that would land on pads or past the board edge, so the placed
  footprints intentionally differ from the library copies.

## Before ordering

- Check part rotations in the assembler's placement preview.
- LCSC numbers are pinned only where checked (crystal, LDO, the 0603
  jellybean parts). JLCPCB matches the rest by MPN; confirm stock.
- A coil's final tuning depends on its surroundings (enclosure, hand,
  cable). The T-match pads let you retune with a nanoVNA.
- Radiated use must follow your region's rules (e.g. FCC 15.231/15.247,
  ETSI EN 300 220).
