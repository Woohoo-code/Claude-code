# Assembly and bring-up

## Order of operations

1. **Stencil + paste** (top only): 0.10-0.12 mm stencil. The U1 exposed pad
   footprint already splits paste into 4 windows (~65% coverage); don't
   replace it with one big aperture, or the part will float and short.
2. **Place** (top): U1, Y1, J1, then all 0402s. Pin 1 of U1 is at the
   top-left, next to the header's pin-1 end, marked by a silk triangle.
3. **Reflow**, lead-free SAC305:
   | Zone | Target |
   |---|---|
   | Preheat | 25 -> 150 C at 1-3 C/s |
   | Soak | 150-200 C for 60-120 s |
   | Time above liquidus (217 C) | 60-90 s |
   | Peak | 245 C (max 260 C, CC1101 MSL3 / 260 C rated) |
   | Cool | < 4 C/s |
   Bake the CC1101 first (125 C, 24 h) if its moisture barrier bag was open
   for more than 168 h (MSL3).
4. **J2** (optional): hand-solder the 1x8 1.27 mm header from the top, or
   solder wires to the pads.
5. Wash flux residue off the RF area (IPA): no-clean residue under 0402s
   can detune the balun slightly.

## Inspection

- X-ray or check under a microscope for bridges across U1's 0.5 mm-pitch
  pins, especially 1-5 and 16-20.
- Check C121/C131 (3.9 pF) against C122 (8.2 pF) and C123 (5.6 pF), and L122
  (22 nH) against the three 27 nH inductors. They look the same and are easy
  to swap.

## Bring-up checklist

1. **Before power**, with a meter:
   - 3V3 (J2.1) to GND (J2.2): > 1 kohm once C1 charges (no short)
   - DCOUPL (C51, U1 side) to 3V3: not a short (a solder bridge here
     would destroy the core)
   - Continuity from J2.3-J2.8 to the matching U1 pins
2. **Current-limited power**: 3.3 V at 50 mA limit. Idle current after
   power-on should be ~1.7 mA (IDLE state, XOSC running).
3. **DCOUPL**: ~1.8 V on C51 (1.6-2.0 V).
4. **SPI**: pull CSn low and wait for SO (MISO) to go low (chip ready), then
   send an SRES strobe (0x30). Read PARTNUM (0xF0) -> 0x00 and VERSION (0xF1)
   -> 0x14 (some older or clone parts report 0x04).
5. **Crystal**: GDO0 defaults to CLK_XOSC/192 (~135 kHz) after reset. Probe
   GDO0 with a scope to confirm the oscillator is running without loading
   the crystal pins.
6. **RF**: load settings from TI SmartRF Studio for 433.92 MHz, PATABLE 0xC0.
   With an attenuator into a spectrum analyzer, expect ~+10 dBm CW. For a
   link test, pair two boards at 1.2-38.4 kBaud.
