# Printed antennas: every CC1101 frequency

> **v1 study, not used by the current board.** The board now uses coil
> (helical spring) antennas at the edge of a 70 x 45 mm PCB; this folder is
> the openEMS model and per-MHz tuning of the earlier 100 x 100 mm version
> with four printed inverted-F antennas, kept for reference.


The CC1101 tunes continuously over **300-348, 387-464 and 779-928 MHz**.
The board has four printed antennas, and each can be tuned to any
frequency in its range with 0603 parts. Values for every MHz are in
[`results/tuning.md`](results/tuning.md) (every 5 MHz) and
`results/tuning_<band>.csv` (every 1 MHz).

| Antenna | Radio | Where | Tunes across | Worst S11 when tuned | Power reaching the antenna |
|---|---|---|---|---|---|
| 315 | A (315 MHz front-end BOM) | left strip, meandered inverted-F | 300-348 MHz | -15.2 dB | 41-65 % |
| 433 | A (433 MHz BOM, fitted) | top strip, inverted-F | 387-464 MHz | -18.1 dB | 76-99 % |
| 868 | B | right strip, upper, inverted-F | 779-880 MHz | -21.3 dB | 97-99 % |
| 915 | B | right strip, lower, inverted-F | 870-928 MHz | -21.6 dB | 97-99 % |

"Power reaching the antenna" is what's left after the losses of the tuning
and match parts (inductor Q 40, capacitor Q 300). The antenna's own
radiation efficiency comes on top of that.

![coverage](results/tuning.png)

On top of the printed antennas, each radio has an SMA jack and a wire hole
for an external whip. Its length for any frequency is in the last table of
`results/tuning.md` (L = 71 250 / f mm).

## How one antenna covers a whole band

Each antenna has two sets of 0603 pads:

- a **tuning element** in series with its arm (L401 = 433, L402 = 315,
  L404 = 868, L405 = 915): an inductor makes the arm electrically longer
  (lower frequency), a capacitor makes it shorter (higher), 0 ohm leaves it
  as drawn;
- a **T-match** at its feed: selector S1 (series), shunt, S2 (series).

## Method

1. **Geometry** (`antenna_geometry.py`) is shared by the model and the
   board generator, so the Gerbers carry exactly the simulated copper.
2. **Full-wave model** (`sim_antenna.py --2port`, openEMS FDTD): the whole
   100 x 100 x 1.6 mm FR4 board (er 4.4, tan d 0.02), both ground layers and
   all four antennas. Port 1 is at the antenna's feed and port 2 across its
   tuning-element gap; the neighbours' tuning elements are modelled as
   0 ohm. This gives the 2-port Z-parameters `results/<band>_z2port.csv`.
3. **Tuning** (`tune.py`): for any tuning part Z_t the feed impedance is
   exactly Zin = Z11 - Z12 Z21 / (Z22 + Z_t). For every MHz the script tries
   0 ohm, every E12 inductor and every E24 capacitor. For each it designs
   the L-section match analytically, snaps it to real part values with their
   losses, and keeps the combination that delivers the most power with
   |S11| < -10 dB. It writes the tables, the plot and `match.py` (the
   board's default fit: 433.92, 315, 868.3 and 915 MHz).

The default fits use only JLCPCB basic / preferred 0603 parts (tune.py
`CHEAP_CAPS`, plus the 39 nH wire-wound on the 315 MHz arm). Their -10 dB
bands: 433: 431.5-436.7 MHz, 315: 313.1-315.8 MHz, 868: 835-880 MHz,
915: 900-1030 MHz. Each covers its ISM band.

## Limits

- **315 MHz is electrically small** here (a quarter wave is 238 mm), so its
  tuning inductor carries real current and loss: 41-65 % of the power
  reaches the antenna. For the longest range at 300-348 MHz use the SMA or
  wire whip.
- Each tuned setting is narrowband (a few MHz at 315/433, tens of MHz at
  868/915). Moving to a new frequency means changing the parts on that
  row of the table.
- The model has no enclosure, hand or cable, which detune a printed
  antenna by a few percent. The trim marks on each antenna's open end and a
  nanoVNA let you correct it: cutting the end raises the frequency.
- Simulated, not yet measured.

## Re-running

```
# openEMS + CSXCAD Python bindings (https://openems.de)
python sim_antenna.py --2port 433 3 52 out/433   # name, tap, tail, outdir
cp out/433/z2port.csv results/433_z2port.csv      # (likewise 315/868/915)
python tune.py                                     # tables, plot, match.py
cd ../pcb && ./make_fab.sh                         # board + Gerbers with new defaults
```
