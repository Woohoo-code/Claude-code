# Pre-order verification

Everything below was run on the final board (`pcb/nano_every_cc1101.kicad_pcb`)
and on the files that go to the fab. `./run_all.sh` re-runs it
(KiCad's Python for extraction, `PY=` a Python with numpy + scipy); full output
in `results.txt`.

| Check | How | Result |
|---|---|---|
| Design rules | KiCad DRC | **0 violations, 0 unconnected pads** |
| Fab limits (JLCPCB 2-layer) | vias 0.25/0.5 and 0.3/0.6 mm, 0.15 mm track/space, PTH rings 0.3-0.5 mm, silk >= 0.15 mm / 1.0 mm high, pad-to-silk >= 0.15 mm | all within limits (no small-via surcharge: pads >= 0.45 mm) |
| Gerber DFM | `gerber_dfm.py` on the zip the fab gets: smallest aperture per layer, drills | **PASS** (silk 0.150 mm, copper 0.150 mm, drills 0.25-1.2 mm) |
| Gerbers readable | parsed with gerbonara and rendered with tracespace (the engine behind web viewers) | 8 layers + 1 drill identified, 70 x 45 mm, 239 holes = 175 vias + 64 THT pads (`gerber_top.png`, `gerber_bottom.png`) |
| Pins vs vendor pin names | `schcheck.py`: every pin of U1/U501 (CC1101), U2 (XC6206), U3 (TXS0108E), Y1/Y501, D1 against JLCPCB's symbols | **all pass**; TXS0108E: VCCA 3.3 V, VCCB 5 V, OE enabled, all 8 channels pair the right radio signal with the right Nano pin |
| Nano Every | all 30 pins vs the ABX00028 datasheet table, outline 43.18 x 17.78 mm | **pass** |
| Placement file | `cplfit.py`: JLCPCB's own footprint of every part fitted onto the board pads, compared with the CPL | **all 66 parts match** (position <= 0.05 mm, rotation exact). This caught U3 (TSSOP), U2 (SOT-23), J3/J4 and S1/S2 needing different angles from KiCad's; the CPL now carries them |
| Assembly preview | `assembly_preview.py`: JLCPCB footprints drawn at the CPL positions over the Gerbers | every part on its pads, pin 1 in the right corner (`assembly_preview.png`) |
| Stock | live JLCPCB stock for 5 boards | all 34 lines in stock; tightest: 12 nH Murata LQW15AN12NJ00D, 85 for 20 needed |
| Decoupling | supply pin -> nearest capacitor | CC1101 1.6-2.8 mm, TXS0108E 1.8 mm, LDO 2.9-3.1 mm |
| Crystal load | 27 pF + 27 pF in series + ~2.5 pF strays vs crystal CL | 15.5-16.5 pF vs 16 pF specified: on frequency |

## Simulations

**Line impedance** (`fieldsolve.py`, 2-D finite-difference electrostatic solver on
the real cross-section: 1.6 mm FR4 er 4.5, 35 um copper, 0.2 mm gap to the top
pour, bottom ground plane; validated on a 3.0 mm microstrip = 50.4 ohm):

| Trace | Use | Z0 | eps_eff |
|---|---|---|---|
| 1.2 mm | antenna buses, selectors, coil feeds | **49.7-51.4 ohm** | 2.59 |
| 0.6 mm | shunt tuning stubs | 59.8 ohm | 2.50 |
| 0.4 mm | balun output (2-3 mm long) | 68.8 ohm | 2.47 |

**Antenna feed networks** (`rfnet.py`: the routed copper as lossy CPWG lines,
0R links 0.03 ohm + 0.5 nH, empty pads 0.1 pF, selected coil 50 ohm at the pour
edge, the other branch and the SMA line as the stubs they are):

| Radio -> coil | S11 at the balun output | Power reaching the coil |
|---|---|---|
| A -> 433 MHz (433.05-434.79) | -26 dB | 98.8 % |
| A -> 315 MHz | -35 dB | 99.1 % |
| B -> 868 MHz (863-870) | -22 dB | 98.0 % |
| B -> 915 MHz (902-928) | -19 dB | 97.4 % |

**CC1101 harmonic filters** (`lpf.py`, TI SWRS061I values with 0402 ESL, Q and
self-resonance):

| Front end | In band | 2nd | 3rd | 4th |
|---|---|---|---|---|
| 433 MHz | -0.8 dB | -22 dB | -41 dB | -58 dB |
| 868 / 915 MHz | -0.5 dB | -17 / -20 dB | -35 / -37 dB | -52 / -57 dB |

(The balun section in front adds further rejection; values are TI's reference.)

**Power** (`power.py`): 65 mA on 3V3 with both radios transmitting at +10 dBm
= 32 % of the XC6206; 110 mW in the LDO, +27 C; 70 mA from the Nano's 5 V pin
(950 mA available).

## Routing

The TXS0108E's rotation, channel order and position were searched (20 + 4 full
autoroute + DRC builds, `detour.py` / `route_metrics.py`): 270 deg with the
channels in the Nano's pin order is shortest.

| | Before | After |
|---|---|---|
| Autorouted copper | 661 mm | **622 mm** |
| Signal vias | 11 | **9** |
| All signal/power copper vs straight-line minimum | x1.24 | **x1.17** |

The Nano pins are unchanged (only which level-shifter channel carries which
signal), so the firmware pin map stays the same.

## Not simulated

The coil antennas themselves: the maker's datasheets give size and band but not
the turn geometry, so they are modelled as the 50 ohm loads they are sold as.
Check them with a nanoVNA once built; each branch has a T-match to retune.
