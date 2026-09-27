# Schematic, by block

There is no `.kicad_sch` for this board; the circuit is small enough to live
here plus `netlist.md`, and the routed PCB is the source of truth for
connectivity. All RF values are the 433 MHz column of TI SWRS061I Table 21.

## 1. CC1101 core (U1)

```
 3V3 ──┬─────────┬──────────┬──────────┬────────── DVDD(4) AVDD(9,11,14,15) DGUARD(18)
       │         │          │          │
      C1 1u    C41 100n   C111 100n  C151 100n  C181 100n     (each within ~1 mm of its pin,
       │         │          │          │          │           ground via beside each cap)
      GND       GND        GND        GND        GND

 DCOUPL(5) ── C51 100n ── GND        (internal 1.8 V regulator; nothing else on this net)
 RBIAS(17) ── R171 56k 1% ── GND
 GND(16,19) + exposed pad ── GND     (5 tented vias in the pad to the In1.Cu plane)
```

- VCC 1.8-3.6 V; every supply pin must be at the same voltage (abs max 3.9 V).
- C41/C111/C151/C181 = 100 nF X7R, one per supply-pin group. AVDD pin 9 sits
  between the two crystal pins with no room for its own cap, so it drops
  straight to the VCC plane and shares C111 (~1.5 mm away).

## 2. Crystal oscillator

```
 XOSC_Q1(8) ──┬── Y1 26 MHz ──┬── XOSC_Q2(10)
              │               │
             C81 27p        C101 27p
              │               │
             GND             GND
```

- CL(effective) = C81*C101/(C81+C101) + ~2.5 pF parasitics = 13.5 + 2.5 = 16 pF,
  matching the YXC X322526MQB4SI (CL 16 pF). For a crystal with a different CL,
  use C81 = C101 = 2 x (CL - 2.5 pF).
- +/-10 ppm crystal: +/-4.3 kHz at 433.92 MHz, fine for 100 kHz channel spacing.
  Frequency offset can be trimmed in software (FSCTRL0).

## 3. Balun + matching (differential RF_P/RF_N to 50 ohm single-ended)

```
 RF_N(13) ──┬──── L131 27n ─────┐
            │                   │
          C131 3.9p             │
            │                   ├── RF_J ── (LC filter)
           GND                  │
 RF_P(12) ──┬──── C121 3.9p ────┘
            │
          L121 27n
            │
          C124 220p   (DC block so L121 doesn't short RF_P's bias)
            │
           GND
```

The low-pass (L131/C131) and high-pass (C121/L121) arms shift the two
differential halves by +/-90 degrees so they add in phase at RF_J.

## 4. LC low-pass filter + DC block

```
 RF_J ── L122 22n ──┬── L123 27n ──┬── C125 220p ── ANT (J1 U.FL, 50 ohm)
                    │              │
                  C122 8.2p      C123 5.6p
                    │              │
                   GND            GND
```

Attenuates the 2nd/3rd harmonics (TI measures -49/-40 dBm conducted at
+10 dBm). C125 blocks DC in case the antenna has a DC path (e.g. a loop).

## 5. Host header (J2, 1x8, 1.27 mm)

| Pin | Signal | Pin | Signal |
|---|---|---|---|
| 1 | 3V3 | 5 | MISO (SO/GDO1) |
| 2 | GND | 6 | GDO2 |
| 3 | MOSI (SI) | 7 | GDO0 |
| 4 | SCK | 8 | CSn |

No series resistors or pull-ups on the module. Keep CSn driven high by the
host whenever the radio is not being addressed; if the host pin floats during
boot, add a pull-up on the host side.
