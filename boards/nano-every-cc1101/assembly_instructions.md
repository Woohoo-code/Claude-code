# Assembly and bring-up

## Ordering (JLCPCB or similar)

1. **PCB:** upload `pcb/fab/nano_every_cc1101-gerbers.zip`. 2 layers, 1.6 mm,
   70 x 45 mm, 1 oz copper, any colour, HASL or ENIG (ENIG is kinder to
   the 0.5 mm-pitch QFNs). Nothing non-standard: 0.15 mm min track/space,
   0.25 mm min drill.
2. **Assembly:** upload `pcb/fab/bom-jlcpcb.csv` and
   `pcb/fab/cpl-jlcpcb.csv`, top side. They contain only the parts to fit
   (not-fitted selectors and match pads are left out), including the four
   coil antennas AE1-AE4, which are through-hole: pick an assembly option
   with through-hole soldering. In the placement preview, **check the
   rotation of U1, U501, U2, U3, Y1 and Y501**: KiCad and JLCPCB disagree
   on some footprint zero angles. The coils must stand upright in their
   holes at the right-hand edge.
3. By hand afterwards: 2x 1x15 female headers (Nano socket). Optional:
   SMA jacks J1/J2 (BWSMA-KE-P001, LCSC C496550; body off the right edge)
   and the 1x15 breakout headers J3/J4 (LCSC C7501269).

## Reflow (if assembling yourself)

Stencil 0.12 mm. Lead-free SAC305 profile: 150-200 C soak 60-120 s,
60-90 s above 217 C, 245 C peak (260 C max, the CC1101 is MSL3: bake at
125 C for 24 h if the bag was open more than a week). Use the footprints'
split paste on the QFN exposed pads.

## Antenna selection (fit exactly one selector per radio)

As shipped: radio A on the 433 MHz coil AE1, radio B on the 868 MHz coil
AE3. All four coils are fitted; moving one 0603 0 ohm part switches band.

| Radio | Antenna | Selector to fit | Leave empty |
|---|---|---|---|
| A (U1) | 433 MHz coil AE1 | R301 | R311, R403 |
| A (U1) | 315 MHz coil AE2 | R311 **and swap to the 315 MHz BOM** (below) | R301, R403 |
| A (U1) | SMA J1 (solder it on) | R403 | R301, R311 |
| B (U501) | 868 MHz coil AE3 | R321 | R331, R406 |
| B (U501) | 915 MHz coil AE4 | R331 | R321, R406 |
| B (U501) | SMA J2 (solder it on) | R406 | R321, R331 |

**Retuning a coil:** each coil branch is selector R3x1, shunt pad C3x1
(empty) and series part L3x1 (0 ohm) right at the coil. With a nanoVNA on
the SMA (fit R403/R406 and the jack) or on the selector pads, add a small
shunt capacitor at C3x1 and/or swap L3x1 for a capacitor or inductor to
centre the coil on another frequency. For frequencies far from the four
coil bands, use the SMA jack with an external antenna (quarter-wave whip
L = 71 250 / f mm).

**315 MHz BOM swap for radio A** (SWRS061I Table 21): C121/C131 6.8 pF,
C122 12 pF, C123 6.8 pF, L121/L123/L131 33 nH, L122 18 nH; C124/C125
stay 330 pF.

## Bring-up

1. Before power, meter: 5V to GND and 3V3 to GND not shorted;
   DCOUPL_A (C51) and DCOUPL_B (C551) not shorted to 3V3.
2. Plug in the Nano (USB toward the board edge). The red LED = 3.3 V OK.
   Radio current at idle ~1.7 mA each.
3. DCOUPL on C51 / C551: ~1.8 V.
4. SPI check for each radio (CSn low -> wait for MISO low -> SRES 0x30 ->
   read PARTNUM 0xF0 = 0x00, VERSION 0xF1 = 0x14):
   radio A CSn = D10, radio B CSn = D9. Keep the unused radio's CSn high.
5. GDO0 defaults to CLK_XOSC/192 (~135 kHz): radio A on D2, radio B on D4.
6. RF: TI SmartRF Studio settings; PATABLE for +10 dBm is 0xC2 (315),
   0xC0 (433), 0xC2 (868), 0xC0 (915) (SWRS061I Table 39), giving
   ~+10 dBm. With a nanoVNA you can check each coil at its selector pads
   and fine-tune its T-match.

## Pin map (Nano Every)

| Function | Nano pin |
|---|---|
| SCK / MOSI / MISO (shared) | D13 / D11 / D12 |
| Radio A CSn / GDO0 / GDO2 | D10 / D2 / D3 |
| Radio B CSn / GDO0 | D9 / D4 |
| Radio B GDO2 | test pad TP1 (3.3 V level, not level-shifted) |
