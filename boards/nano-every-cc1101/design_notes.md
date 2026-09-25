# Design notes

## Why two radios

The CC1101 covers 300-348, 387-464 and 779-928 MHz, but its RF pins need a
band-specific balun + filter, and TI's 315/433 MHz and 868/915 MHz networks
are different topologies (SWRS061I Fig. 10 vs Fig. 11), not just different
values. One CC1101 can therefore only be good in one band group. This board
carries two:

| Radio | Chip | Front end | Bands | Antennas |
|---|---|---|---|---|
| A | U1 | Fig. 10 (L/C balun + LC low-pass), 433 MHz values fitted | 387-464 MHz; 300-348 MHz after the 315 MHz BOM swap | PCB 433 (top edge), PCB 315 (left edge), SMA J1, wire H1 |
| B | U501 | Fig. 11 (wire-wound balun + LC low-pass) | 779-928 MHz | PCB 868 and PCB 915 (right edge), SMA J2, wire H2 |

Both share SPI (SCK/MOSI/MISO; the CC1101's SO pin is high-impedance while
CSn is high) and have their own CSn and GDO0. Radio A also has GDO2 on the
Nano; radio B's GDO2 goes to test pad TP1, because the one TXS0108E has 8
channels and that is the ninth signal.

## Board

| Item | Value |
|---|---|
| Size | 100 x 100 mm (the cheapest fab price tier) |
| Layers | **2**: F.Cu parts + routing + ground pour, B.Cu ground plane + a few routes |
| Thickness | 1.6 mm FR4 |
| Min track / space | 0.15 / 0.15 mm (0.15 mm only inside the two CC1101 clusters) |
| Vias | 0.6 / 0.3 mm; 0.5 / 0.25 mm inside the CC1101 clusters |
| Ground | solid pour on both layers over the 60 x 80 mm ground region, 223 ground vias |
| Antenna strips | copper-free: top 100 x 20 mm, left 22 x 80 mm, right 18 x 80 mm |

## RF layout

- Each CC1101 cluster is the routed layout from `boards/cc1101-mini`: QFN
  with 5 tented vias in the exposed pad, a 100 nF cap and via on every
  supply pin, and the crystal on its own short traces. The mini used a
  4-layer VCC plane; here a short B.Cu ring links the chip's AVDD/DGUARD
  vias instead, and 3.3 V arrives on top-layer traces.
- Radio B keeps the same core and replaces the balun with TI's 868/915 MHz
  network (L131/L121 series, C121 across, C131 + L132, L122 + C124 + C122,
  then L123-C123-L124-C125).
- 50 ohm lines are 1.2 mm grounded coplanar waveguide with 0.2 mm gaps
  (51 ohm on 1.6 mm FR4) over the unbroken B.Cu ground, with stitching vias
  along both sides wherever they fit.
- Each T-match sits within ~3 mm of its antenna feed, so the simulated
  feed impedance is what the match sees.
- The B.Cu ground plane is kept free of routing under both RF paths, all
  match networks and the SMA lines (Freerouting keep-outs).

## Antennas

See `antenna/README.md`. Four inverted-F antennas (the 315 MHz one
meandered) each carry a series tuning element in the arm plus a T-match at
the feed. A 2-port openEMS model of the whole board (feed + tuning gap)
gives the exact feed impedance for any tuning part, so `tune.py` can pick
the parts for **every MHz** of 300-348, 387-464 and 779-928 MHz. It reaches
S11 below -15 dB everywhere, with 41-65 % of the power reaching the antenna
at 300-348 MHz and 76-99 % elsewhere.

## Level shifting and power

- The Nano Every is 5 V logic; the CC1101 is 3.6 V max. A TXS0108E
  (auto-direction, 3.3 V A side, 5 V B side) sits between them.
- AP2112K-3.3 LDO from the Nano's 5 V pin: 600 mA available, two radios
  in TX draw ~60 mA.

## Autorouting

Freerouting only routes the non-RF signals (SPI, CSn/GDO, 3.3 V/5 V, LED).
Everything RF, both CC1101 clusters, every match network, antenna and
power stub is placed and routed by `pcb/gen_board.py` itself. Ground is
never routed: every ground pad has its own via into both pours.

## DRC

`pcb/drc_report.txt`: 0 errors and 0 unconnected pads. The warnings left
are all expected:
- the four antennas' open ends ("track has unconnected end"),
- decoupling caps inside the QFN courtyards (C51/C111/C551/C611),
- library silkscreen outlines touching.

## Before ordering

- Check part rotations in the assembler's placement preview.
- LCSC numbers are pinned only where checked (crystal, LDO, the 0603
  jellybean parts). JLCPCB matches the rest by MPN; confirm stock.
- A printed antenna's final tuning depends on its surroundings (enclosure,
  hand, cable). The tuning and T-match pads let you retune with a nanoVNA.
- Radiated use must follow your region's rules (e.g. FCC 15.231/15.247,
  ETSI EN 300 220).
