# Printed antennas: design and tuning

Four printed antennas share the board's three copper-free edges:

| Antenna | Radio | Where | Type | Notes |
|---|---|---|---|---|
| 433 MHz | A | top strip, 100 x 20 mm | inverted-F | fitted by default (R301) |
| 315 MHz | A | left strip, 22 x 80 mm | meandered monopole, base-loaded | needs the 315 MHz BOM on radio A |
| 868 MHz | B | right strip, upper | inverted-F | fitted by default (R321); covers 863-870 MHz |
| 915 MHz | B | right strip, lower | inverted-F (mirrored) | covers 902-928 MHz |

The exact geometry (trace centrelines, 1.5 mm wide) is in
`antenna_geometry.py`, which both the simulation and the board generator
import. What was simulated is exactly what is on the Gerbers.

## Method

1. **Full-wave model** (`sim_antenna.py`, openEMS FDTD): the whole
   100 x 100 x 1.6 mm FR4 board (er 4.4, tan d 0.02), both ground layers
   and **all four antennas** in every run. One antenna is driven by a 50 ohm
   port at its feed; the others' feeds are left open, as they are on the
   board when their selector isn't fitted. PML boundaries, run down to -30 dB.
2. **Length tuning**: each arm's last segment (`tail`) and the inverted-F
   feed-to-short spacing (`tap`) were iterated until the antenna resonates
   in its band with a feed impedance a mild match can handle. Each run's
   Zin(f) is kept in `results/<band>.csv`.
3. **T-match** (`design_match.py`): from that Zin, pick an L-section
   (selector S1 + shunt C + series S2) from standard E12/E24 0603 values
   that minimises the worst |S11| over +/-1 % of the band centre. The loss
   of realistic parts (inductor Q 40, capacitor Q 300) is included, and the
   power lost in the match is reported. The values are written to
   `match.py`, which the board generator uses for the part values.

Results: `results/summary.md` (table) and `results/match.png` (S11 of each
antenna alone and with its T-match).

## Honest limits

- The 315 MHz quarter wave is 238 mm; the left strip allows about 210 mm
  of meander, which is electrically short. It runs as a base-loaded
  monopole (R402 short left open, loading coil = S2 of its T-match). It
  matches, but a real loading coil's loss costs efficiency (see the match
  loss column). For best 315 MHz range use the SMA/wire option (226 mm whip).
- The model has no enclosure, hand or USB cable. Those detune printed
  antennas by a few percent. The T-match pads (and the 2 mm trim marks on
  each antenna's open end) are there to re-tune: cutting the end raises
  the frequency.
- Simulated, not yet measured. Check with a nanoVNA at the selector pad:
  disconnect the radio side by lifting S1's node-side pad, or measure
  through the SMA option.

## Re-running

```
# openEMS + CSXCAD Python bindings (https://openems.de)
python sim_antenna.py 433            # uses PARAMS from antenna_geometry.py
python sim_antenna.py 433 3 52 out/  # try tap=3 mm, tail=52 mm
cp out/s11.csv results/433.csv
python design_match.py               # rewrites match.py + results/
cd ../pcb && ./make_fab.sh           # regenerate the board with new values
```
