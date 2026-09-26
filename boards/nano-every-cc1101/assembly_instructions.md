# Assembly and bring-up

## Ordering (JLCPCB or similar)

1. **PCB:** upload `pcb/fab/nano_every_cc1101-gerbers.zip`. 2 layers, 1.6 mm,
   70 x 45 mm, 1 oz copper, any colour, HASL or ENIG (ENIG is kinder to
   the 0.5 mm-pitch QFNs). Nothing non-standard: 0.15 mm min track/space,
   0.25 mm min drill.
2. **Assembly:** upload `pcb/fab/bom-jlcpcb.csv` and
   `pcb/fab/cpl-jlcpcb.csv`, top side. **Everything except the Nano Every
   is assembled:** all SMD parts, the four coil antennas AE1-AE4, the SMA
   jacks J1/J2, the breakout headers J3/J4 and the Nano sockets S1/S2
   (two 1x15 female headers, LCSC C7499333, in the Nano's own holes).
   Not-fitted selectors and match pads are left out. Choose **Economic
   PCBA** (Standard needs 70 x 70 mm or larger); it solders the through-hole
   coils, headers and sockets and needs no rails or fiducials. The CPL
   already carries JLCPCB's own footprint angles (KiCad and JLCPCB differ
   for the TSSOP, the SOT-23, the headers and the sockets; every part was
   fitted onto JLCPCB's footprint, `verify/VERIFICATION.md`), so the
   preview should show every part on its pads, and the SMA bodies and all
   four coils pointing off the right edge. The coils are bent-leg spring
   antennas, built to lie in the board plane beyond an edge: their leg goes
   through a hole 2 mm from the edge and the coil sticks out past it.
   Suggested PCBA remark: *"AE1-AE4 are bent-leg spring antennas: leg through the hole, coil lying flat beyond the right board edge, as in the 3D preview. J1/J2 (SMA edge jacks): please also solder the two bottom-side ground legs."*
   The SMA jacks are reflowed from the top; if their two bottom ground legs
   come back unsoldered, solder those four joints before using a jack.
3. Afterwards: The Nano Every ABX00028 comes with its two 1x15 headers **loose** in the
   box; solder them on first. Easiest way to get them straight: push the
   headers (long pins down) into S1/S2 on this board, lay the Nano on top,
   solder the 30 pins on the Nano, then pull it out. Plug it into S1/S2 with
   USB toward the board edge (D12/D13 end at the edge). ABX00033 is the same
   Nano with the headers already soldered. Checked against the ABX00028
   datasheet: 2 x 15 pins, 2.54 mm pitch, rows 15.24 mm apart, 43.18 x
   17.78 mm, same pin order.

## Reflow (if assembling yourself)

Stencil 0.12 mm. Lead-free SAC305 profile: 150-200 C soak 60-120 s,
60-90 s above 217 C, 245 C peak (260 C max, the CC1101 is MSL3: bake at
125 C for 24 h if the bag was open more than a week). Each QFN exposed pad
has four paste windows (0.85 mm, ~50 % coverage) between its five vias,
which are tented on the component side as TI specifies, so no solder runs
down them.

## Antenna selection (fit exactly one selector per radio)

As shipped: radio A on the 433 MHz coil AE1, radio B on the 868 MHz coil
AE3. All four coils are fitted; moving one 0603 0 ohm part switches band.

| Radio | Antenna | Selector to fit | Leave empty |
|---|---|---|---|
| A (U1) | 433 MHz coil AE1 | R301 | R311, R403 |
| A (U1) | 315 MHz coil AE2 | R311 **and swap to the 315 MHz BOM** (below) | R301, R403 |
| A (U1) | SMA J1 | R403 | R301, R311 |
| B (U501) | 868 MHz coil AE3 | R321 | R331, R406 |
| B (U501) | 915 MHz coil AE4 | R331 | R321, R406 |
| B (U501) | SMA J2 | R406 | R321, R331 |

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
