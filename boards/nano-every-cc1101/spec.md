# Board spec

## Function
Carrier board for an Arduino Nano Every that adds TI CC1101 sub-GHz radios
covering every band the CC1101 supports (300-348, 387-464 and 779-928 MHz),
with an antenna for every band.

## Inputs / outputs
- Arduino Nano Every in 2x 1x15 2.54 mm sockets; USB on the board edge
- Every Nano pin broken out again on two 1x15 2.54 mm male headers
- Printed antennas: 315, 433, 868 and 915 MHz (inverted-F, openEMS-tuned)
- External antennas: one SMA edge jack and one wire-whip hole per radio

## Power
- From the Nano's 5 V (USB or VIN); on-board 3.3 V LDO for the radios
- Radio current: ~30 mA per radio in TX at +10 dBm, ~16 mA RX

## Key components
- 2x CC1101RGPR: radio A with the 315/433 MHz front end (433 fitted),
  radio B with the 868/915 MHz front end
- TXS0108E 3.3 V <-> 5 V level shifter (the Nano Every is 5 V logic)
- AP2112K-3.3 LDO

## Constraints
- **2 layers** (cheapest), 1.6 mm FR4, up to 100 x 100 mm
- Print ready: Gerbers + drills + JLCPCB BOM/CPL, within standard
  2-layer rules (0.15 mm track/space, 0.3 mm vias outside the CC1101 area)

## Notes
- Antenna selection by fitting one 0603 selector per radio
