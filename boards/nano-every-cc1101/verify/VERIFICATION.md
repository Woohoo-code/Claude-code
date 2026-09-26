# Pre-order verification

Everything below was run on the final board (`pcb/nano_every_cc1101.kicad_pcb`,
v2.2) and on the files that go to the fab. `./run_all.sh` re-runs it (KiCad's
Python for extraction, `PY=` a Python with numpy + scipy + shapely + gerbonara;
`ONLINE=1` adds the live LCSC checks, `FULLWAVE=1` the openEMS simulation);
full output in `results.txt`.

## What the final recheck found and fixed

A second, deeper pass with checks that do not rely on KiCad or on the board
generator turned up these, all fixed in v2.2:

| Found | Why it mattered | Fix |
|---|---|---|
| The 315, 433 and 915 MHz coils are the maker's **bent-leg** type: the leg is at right angles to the coil. Their drawings and JLCPCB's 3D models show the coil lying in the board plane with its axis at the copper surface, i.e. beyond a board edge. The board assumed all four stand upright (only the straight-leg 868 MHz coil did). | Assembled as designed, three coils would have had to lie across the board or be bent by hand. | New footprints: hole 2 mm from the right edge, coil pointing off the edge (courtyard checked against the SMA jacks: 1.3 mm or more), CPL angle fitted to JLCPCB's own outline so their preview shows each coil pointing off the edge. |
| The makers' own measurements: BAT WIRELESS 868 MHz coil **VSWR 5.32** at 868 MHz (3.3 dB return loss, 28 % efficiency), 915 MHz coil VSWR 2.62. | Half the 868 MHz power reflected before any retuning. | Radio B now uses Vollgo VG868SNX18-5W2 (C718843, measured VSWR 1.32 at 868 MHz) and VG915SNX17-5W2 (C718842, 1.56 at 915 MHz), both bent-leg, 1.1 mm holes for their 0.75-0.8 mm wire. 433 MHz (1.32) and 315 MHz (2.49; no stocked alternative) stay. |
| The CC1101 exposed-pad vias were open and sat right under KiCad's four paste squares. | TI's CC1101 layout recommendations: tent the exposed-pad vias on the component side so solder does not migrate down them. | Vias moved to a + pattern, tented; mask and paste opened only in four 0.85 mm windows between them (50 % paste). |
| DCOUPL cap C51/C551: body 0.1 mm from the QFN, pad 0.065 mm from pin 5 (below JLCPCB's 0.10 mm solder-mask bridge). | Placement margin; solder could pull the cap onto pin 5. | C51 moved to 0.30 mm body / 0.215 mm pad clearance, a 0.22 mm mask web. C41 and C111 moved to make room. |
| Five ground vias touched their pad's mask opening (a sliver of via ring exposed). | Solder wicking at 0402 pads (tombstoning risk). | Every escape via now sits 0.1 mm or more outside its pad's opening; checked on the Gerbers: 0 exposed vias. |
| 12 nH LQW15AN12NJ00D (C82920): 85 in stock, 20 needed for 5 boards. | Order could fail on stock. | LQW15AN12NG00D (C86128): same Murata wire-wound series, +/-2 % instead of +/-5 %, 32 865 in stock. |
| Coil holes were 1.2 mm; the BAT WIRELESS datasheets give 0.5 mm wire. | Loose fit. | 1.0 mm holes (JLCPCB's own 433 MHz footprint uses 1.0); 1.1 mm for the Vollgo coils. |
| Example sketch used a 58 kHz receive filter. | Two boards' +/-10 ppm (+/-20 ppm over temperature) crystals can be 20-50 kHz apart at 868 MHz. | 135 kHz (RadioLib's default). |
| VERIFICATION listed 239 holes / 175 vias from an earlier build. | Stale numbers. | Regenerated here from the files. |

## Checks

| Check | How | Result |
|---|---|---|
| Design rules | KiCad DRC | **0 violations, 0 unconnected pads, 0 footprint errors** |
| **Netlist from the fab files alone** | `gerber_nets.py`: copper polygons rebuilt from the Gerbers (gerbonara + shapely), joined through every plated hole of the drill file, every KiCad pad and via located in them | **all 73 nets present, 0 shorts, 0 opens, 0 floating copper**; 423/423 pads + vias found |
| Fab limits measured on the Gerbers | same script, against JLCPCB's published 2-layer limits (Sep 2026) | copper gap >= 0.150 mm (min 0.10); copper to edge >= 0.2 mm; PTH rings >= 0.300 mm (min 0.18, rec. 0.25); via rings 0.125 mm; hole to hole >= 0.457 mm (vias, min 0.2) / 1.54 mm (pads, min 0.45); via hole to other-net copper >= 0.275 mm (min 0.2); pad hole to other-net copper >= 0.50 mm (min 0.28) |
| Solder mask and paste on the Gerbers | same script | every pad opened (the two exposed pads deliberately only through their windows); **0 vias exposed**; narrowest mask web 0.22 mm (min 0.10); no opening within 0.09 mm of another net; paste on every SMD pad (not TP1, a bare test pad), none on through-hole pads |
| Gerber apertures / drills | `gerber_dfm.py` | **PASS** (silk 0.150 mm, copper 0.150 mm, drills 0.25 / 0.30 / 1.00 / 1.10 mm) |
| Gerbers readable | gerbonara + tracespace (the engine behind web viewers) | 8 layers + 1 drill, 70 x 45 mm, 215 holes = 151 vias + 64 through-hole pads; drills 0.25 / 0.30 / 1.0 / 1.1 mm (`gerber_top.png`, `gerber_bottom.png`) |
| **Part spacing** | `spacing.py`: every pair of the 56 assembled SMD parts against JLCPCB's "Minimum Spacing Requirements for SMD Components" table (body + pads, as their drawing measures) | **0 pairs below the table.** Next to the CC1101s the parts follow TI's reference placement (decoupling and balun at the pins), closer than JLCPCB's general 1 mm QFN inspection allowance: every body 0.30 mm or more and every pad 0.215 mm or more from the package |
| Pins vs vendor pin names | `schcheck.py`: CC1101 x2, XC6206, TXS0108E, crystals, LED against JLCPCB's symbols; Nano against the ABX00028 datasheet | **all pass**; TXS0108E VCCA 3.3 V, VCCB 5 V, OE enabled, all 8 channels pair the right signal with the right Nano pin |
| **Firmware pin map** | `fwtrace.py`: each pin in `dual_cc1101.ino` traced Nano pin -> TXS0108E channel -> CC1101 pin on the routed board | **matches** (CSn/GDO0/GDO2 of both radios, SCK/MOSI/MISO to both) |
| Firmware builds | arduino-cli, arduino:megaavr 1.8.8, RadioLib 7.7.1 | 25 689 B flash (52 %), 1 269 B RAM (20 %) |
| Placement file | `cplfit.py`: JLCPCB's own footprint of every part fitted onto the board pads (and, for parts with a direction, onto their outline), compared with the CPL | **all 66 parts match** (position <= 0.05 mm, rotation exact, coils pointing off the edge) |
| Assembly preview | `assembly_preview.py`: JLCPCB footprints and outlines drawn at the CPL positions over the Gerbers | every part on its pads, pin 1 right, SMA bodies and bent-leg coils past the right edge (`assembly_preview.png`) |
| **Parts vs LCSC** | `partcheck.py`: every BOM line against its live LCSC record | **all 34 lines match** (value, package, part number); RF capacitors C0G/NP0, crystal 26 MHz 16 pF +/-10 ppm ESR 50 ohm |
| Holes vs makers' drawings | coil, header and socket datasheets | coil wire 0.5 mm -> 1.0 mm hole, 0.75-0.8 mm -> 1.1 mm; header 0.64 mm square pin and socket 0.64 x 0.4 mm tail, makers recommend 1.02 mm -> 1.0 mm |
| Stock | live JLCPCB stock for 5 boards | all 34 lines in stock; the tightest is the 915 MHz coil, 1 524 for 5 |
| Decoupling | supply pin -> nearest capacitor | CC1101 1.6-2.8 mm, TXS0108E 1.8 mm, LDO 2.9-3.1 mm |
| Crystal load | 27 pF + 27 pF in series + ~2.5 pF strays vs crystal CL | 15.5-16.5 pF vs 16 pF specified |

## Simulations

**Line impedance, two independent methods** on the real cross-section (1.6 mm
FR4 er 4.5, bottom ground plane, top ground pour at a 0.2 mm gap):

| Method | Copper | 1.2 mm line Z0 | eps_eff |
|---|---|---|---|
| 2-D finite-difference field solver (`fieldsolve.py`, validated on a 3.0 mm microstrip = 50.4 ohm) | 35 um | **49.7 ohm** | 2.59 |
| same | zero thickness | 52.2 ohm | 2.70 |
| 3-D full-wave FDTD, openEMS (`fullwave_cpwg.py`, 50 mm line between two ports, 0.3-1.0 GHz, converged to -50 dB) | zero thickness | **51.8 ohm** (51.4-52.1) | 2.84 |

The full-wave result is 0.4 ohm from the 2-D solver for the same geometry
(S11 into 50 ohm <= -30 dB, S21 0.00 dB), so the 49.7 ohm for the real
copper stands. The 0.6 mm tuning stubs are 59.8 ohm and the 0.4 mm balun
output 68.8 ohm (2-3 mm long).

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

The TXS0108E's rotation and channel order were searched again after the
v2.2 changes (20 full autoroute + DRC builds): 270 deg with channel order 4
is the shortest DRC-clean layout with the fewest vias.

| | v2.1 build | v2.2 |
|---|---|---|
| Autorouted copper | 622 mm | **644 mm** (the moved CC1101 parts and exposed-pad vias cost 22 mm) |
| Signal vias | 9 | **11** |
| All signal/power copper vs straight-line minimum | x1.17 | **x1.20** |

Only which level-shifter channel carries which signal changed; the Nano pins,
and so the firmware, are the same (`fwtrace.py`).

## Not simulated / residual risks

- **The coils themselves.** The makers give size, band and a measured VSWR
  on their own test fixture (433 MHz 1.32, 315 MHz 2.49, 868 MHz 1.32,
  915 MHz 1.56) but no model, so they are the 50 ohm loads they are sold as.
  On this board the numbers will shift: check each with a nanoVNA once
  built; each branch has a T-match to retune. The 315 MHz coil passes 1.3 mm
  from the SMA J1 body, which may pull it slightly.
- The coils stick out past the right edge (up to ~41 mm), which is their
  intended mounting; they need room in an enclosure.
- The SMA jacks are reflowed from the top; their two bottom ground legs need
  hand soldering (PCBA remark, or four joints yourself) before a jack is used.
- Next to the CC1101s the parts are closer than JLCPCB's general 1 mm QFN
  recommendation (an inspection / rework allowance), as TI's layout needs;
  bodies are 0.30 mm or more apart.
