# Design notes

## Board

| Item | Value |
|---|---|
| Size | **18.5 x 12.6 mm**, 1.6 mm thick |
| Layers | 4: F.Cu signals + GND pour / In1.Cu solid GND / In2.Cu VCC plane / B.Cu escape routes + GND pour |
| Stackup | JLCPCB JLC04161H-7628 (L1-L2 prepreg 0.2104 mm, er ~4.4) or equivalent |
| Min track / space | 0.127 mm design rule; 0.15 mm used everywhere |
| Vias | 0.45 mm pad / 0.2 mm drill, tented |
| Finish | ENIG recommended (flat pads for the 0.5 mm-pitch QFN and 0402s) |
| Assembly | All SMT on top; only J2 is through-hole |

## Layout

```
 ┌──────────────────────────────────────┐
 │ J2  C1  C181 R171 C151        ┌────┐ │
 │ 1         ┌───────┐   C131    │ J1 │ │   ANT
 │ .         │       │  L131     │U.FL│ │
 │ .   C41   │  U1   │  C121─L122─L123─C125
 │ .   C51   │CC1101 │  L121     C122 C123
 │ 8         └───────┘  C111 C124       │
 │      C81  [ Y1 26MHz ]  C101         │
 └──────────────────────────────────────┘
```

- Digital lines leave U1 to the left, drop through a via right at the pin and
  run to J2 on B.Cu, so the top layer around the chip is decoupling caps + pour.
- Every VCC pin gets a via to the In2.Cu plane at the pin, with its 100 nF
  cap on the same short stub. Every decoupling/shunt cap gets its own ground
  via next to its GND pad.
- RF runs left-to-right on F.Cu over the unbroken In1.Cu ground plane, as
  grounded coplanar waveguide: 0.40 mm track, 0.25 mm gap to the top pour,
  0.21 mm to the reference plane, which works out to **~49 ohm**
  (0.36 mm would be ~52 ohm). The balun section (U1 to RF_J) is 0.25 mm; it is
  a few mm long at 433 MHz (lambda ~ 345 mm in the board), so it is lumped.
- Crystal traces are < 3.5 mm, over solid ground, with no digital lines on
  top or bottom under them (SWRS061I section 7.3). XOSC_Q1 runs between the
  crystal's pads; it is the crystal's own net, not an aggressor.
- 5 tented vias in the exposed pad, as in the TI reference design (7.8).
  Paste coverage on the pad is reduced to 4 windows by the footprint.
- ~40 ground stitching vias on a 1.3 mm grid tie the three ground layers
  together; they are placed only where they clear all other nets by >= 0.2 mm.

## Power / current

| Mode | Typical current (3.0 V) |
|---|---|
| TX, +10 dBm (PATABLE 0xC0 at 433 MHz) | 29 mA |
| RX | 15-17 mA |
| Sleep | 0.2 uA |

Header and planes carry this trivially; the 0.25 mm VCC stubs are good for
~1 A. The host 3.3 V rail should supply >= 50 mA with < 50 mV ripple.

## DRC

`pcb/drc_report.txt` (KiCad 7 DRC, run via `pcbnew.WriteDRCReport`):
**0 errors, 0 unconnected pads, 5 warnings**, all cosmetic and accepted:

- 2x courtyard overlap: C51 and C111 sit inside U1's IPC courtyard (which
  extends 0.63 mm past the pad tips). That's normal for decoupling caps on a
  QFN; the parts themselves have >= 0.2 mm copper clearance.
- 2x silkscreen clipped by solder mask, 1x silkscreen overlap: library silk
  outlines of Y1/C51 touching; the fab clips silk off pads automatically.

## Design decisions (not dictated by the spec)

- **4 layers instead of 2**: gives the CC1101 an unbroken ground reference
  under the RF path and a VCC plane, which makes a 0.5 mm-pitch QFN with six
  supply pins routable in this footprint. At JLCPCB-class fabs, 4-layer
  prototypes cost only a few dollars more than 2-layer.
- **433 MHz multilayer-inductor BOM** (LQG15HS), as in TI's 433 MHz
  reference. Expect ~+10 dBm max output.
- **U.FL instead of a PCB antenna**: a quarter-wave at 433 MHz is ~17 cm, so an
  on-board antenna would be very inefficient at this size. Use a U.FL pigtail
  to an SMA 433 MHz whip, or a spring antenna.
- **1.27 mm 1x8 header**: a 2.54 mm header would be ~21 mm long, longer than
  the board. The header is optional; the pads also take wires.
- **No regulator/level shifting**: the host supplies 1.8-3.6 V and the
  CC1101's I/O runs at that voltage.
- **Crystal**: YXC X322526MQB4SI (26 MHz, +/-10 ppm, CL 16 pF) instead of
  TI's NDK NX3225GA: it's stocked at LCSC/JLCPCB, and CL 16 pF keeps TI's
  27 pF load caps unchanged.

## 868 / 915 MHz variant

This layout is **433 MHz only**. The 868/915 MHz reference (SWRS061I Figure 11)
uses a different balun topology (adds L132, moves C122/L122 into the balun,
adds optional C126/L125) and wire-wound inductors. That is a re-layout, not a
BOM swap. The 315 MHz BOM (same topology as 433) *is* a drop-in: see Table 21.

## Before ordering

- Confirm stock/MPNs at your assembler (JLCPCB/LCSC numbers aren't pinned
  except for Y1).
- Check component rotations in the assembler's placement preview: KiCad and
  JLCPCB disagree on the zero-rotation of some footprints (QFN, U.FL, crystal).
- Pre-compliance test before any radiated use (FCC 15.231 / ETSI EN 300 220).
