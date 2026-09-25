# Netlist

Extracted from the routed board (`pcb/cc1101_mini.kicad_pcb`), which DRC reports
as fully connected (0 unconnected pads). U1 pin numbers are CC1101 pins
(SWRS061I Table 2); J2 pins are header positions (pin 1 = square pad).

## Power

| Net | Connections | Notes |
|---|---|---|
| VCC (3V3) | J2.1, U1.4 (DVDD), U1.9 (AVDD), U1.11 (AVDD), U1.14 (AVDD), U1.15 (AVDD), U1.18 (DGUARD), C1.1, C41.2, C111.2, C151.1, C181.2 | Distributed on the In2.Cu plane; 1.8-3.6 V |
| GND | J2.2, U1.16, U1.19, U1.21 (exposed pad), J1.2 (U.FL shell), Y1.2, Y1.4, C1.2, C41.1, C51.1, C81.1, C101.1, C111.1, C122.1, C123.1, C124.1, C131.2, C151.2, C181.1, R171.2 | Solid In1.Cu plane + F.Cu/B.Cu pours, stitched |
| DCOUPL | U1.5, C51.2 | 1.8 V on-chip regulator output. **Do not connect to VCC or load it** |

## SPI + GPIO (to host)

| Net | Connections | Direction (w.r.t. CC1101) |
|---|---|---|
| SI (MOSI) | U1.20, J2.3 | in |
| SCLK | U1.1, J2.4 | in, 10 MHz max (6.5 MHz burst) |
| SO (MISO / GDO1) | U1.2, J2.5 | out |
| GDO2 | U1.3, J2.6 | out (configurable) |
| GDO0 | U1.6, J2.7 | in/out (configurable; also ATEST) |
| CSN | U1.7, J2.8 | in, active low |

## Analog support

| Net | Connections | Notes |
|---|---|---|
| RBIAS | U1.17, R171.1 | 56 kohm 1% to GND |
| XOSC_Q1 | U1.8, Y1.1, C81.2 | 27 pF to GND |
| XOSC_Q2 | U1.10, Y1.3, C101.2 | 27 pF to GND |

## RF (433 MHz balun + LC filter, SWRS061I Figure 10)

| Net | Connections | Notes |
|---|---|---|
| RF_P | U1.12, C121.1, L121.2 | |
| RF_N | U1.13, L131.1, C131.1 | |
| RF_L121 | L121.1, C124.2 | L121 shunt to GND through DC-block C124 |
| RF_J | L131.2, C121.2, L122.1 | Balun combining node (single-ended from here) |
| RF_F1 | L122.2, L123.1, C122.2 | |
| RF_F2 | L123.2, C125.1, C123.2 | |
| ANT | C125.2, J1.1 | 50 ohm to the U.FL |
