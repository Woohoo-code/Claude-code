# Board spec

## Function
Tiny breakout / drop-in radio module for the TI CC1101 sub-1 GHz transceiver,
tuned for the 433 MHz ISM band (433.05-434.79 MHz). The host MCU talks to it over
SPI; the module has no MCU of its own.

## Inputs / outputs
- 1x8, 1.27 mm pitch through-hole header on one short edge:
  3V3, GND, MOSI (SI), SCK, MISO (SO/GDO1), GDO2, GDO0, CSn
- U.FL (Hirose U.FL-R-SMT-1) 50 ohm antenna connector

## Power
- Single 1.8-3.6 V rail supplied by the host (nominally 3.3 V), no on-board regulator
- Budget: ~30 mA TX at +10 dBm, ~16 mA RX, 200 nA sleep; the host rail must supply >= 50 mA

## Key components
- TI CC1101RGPR (4x4 mm QFN-20)
- 26 MHz, +/-10 ppm, 3.2x2.5 mm crystal
- TI datasheet 315/433 MHz reference balun + LC low-pass filter, 0402 parts

## Constraints
- As small as practical: target under 20 x 13 mm
- 4-layer, 1.6 mm FR4 (JLCPCB JLC04161H-7628 or equivalent), single-sided SMT assembly
- 0402 passives, 0.2 mm / 0.45 mm vias, 0.127 mm (5 mil) minimum track/space

## Notes
- The RF front end follows SWRS061I Figure 10 / Table 21 (433 MHz column) exactly;
  868/915 MHz needs a different BOM *and* topology (see design_notes.md)
