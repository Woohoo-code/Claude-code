#!/usr/bin/env python3
"""Pick the 315 MHz antenna's loading inductor from its 2-port model.

sim_antenna.py --2port gives Z-parameters with port 1 at the feed and
port 2 across the gap where the loading coil sits. For any coil Z_L
(including its loss, Q ~ 40) the feed impedance is

    Zin = Z11 - Z12 * Z21 / (Z22 + Z_L)

so every standard inductor value can be evaluated without re-simulating.
For each value this designs the T-match (design_match.design) and reports
S11 plus total efficiency (coil loss x match loss). The best value's Zin is
written to results/315.csv; set PARAMS["315"]["load_nh"] to it.

Usage: python choose_load.py <z2port.csv>
"""

import csv
import math
import os
import sys

import numpy as np

import design_match as dm

HERE = os.path.dirname(os.path.abspath(__file__))
Q_COIL = 40.0
VALUES_NH = [22, 27, 33, 39, 47, 56, 68, 82, 100, 120, 150, 180, 220]


def load(path):
    rows = list(csv.reader(open(path)))[1:]
    a = np.array([[float(v) for v in r] for r in rows])
    f = a[:, 0] * 1e6
    z = {k: a[:, 1 + 2 * i] + 1j * a[:, 2 + 2 * i]
         for i, k in enumerate(("11", "12", "21", "22"))}
    return f, z


def main():
    f, z = load(sys.argv[1])
    w = 2 * np.pi * f
    f0 = 315e6
    i0 = int(np.argmin(np.abs(f - f0)))
    best = None
    print(" L(nH)  Zin@315            S11(match)  coil+match eff")
    for nh in VALUES_NH:
        zl = 1j * w * nh * 1e-9 + w * nh * 1e-9 / Q_COIL
        zin = z["11"] - z["12"] * z["21"] / (z["22"] + zl)
        # current into the coil per unit feed current -> coil loss
        i2 = -z["21"] / (z["22"] + zl)
        p_in = np.real(zin)
        p_coil = np.abs(i2) ** 2 * np.real(zl)
        eff_coil = float(np.clip(1 - p_coil[i0] / p_in[i0], 0, 1)) if p_in[i0] > 0 else 0.0
        path = os.path.join(HERE, "results", "315.csv")
        np.savetxt(path, np.column_stack([f / 1e6, 20 * np.log10(np.abs(dm.gamma(zin))),
                                          zin.real, zin.imag]),
                   delimiter=",", header="f_MHz,S11_dB,Re_Zin,Im_Zin", comments="")
        r = dm.design("315")
        total = eff_coil * r["eff"]
        print(f"{nh:5d}  {zin[i0].real:7.1f}{zin[i0].imag:+8.1f}j  {r['s11_0']:7.1f} dB"
              f"   {total * 100:5.1f} %")
        score = total if r["s11_0"] < -15 else total - 1   # want a robust match
        if best is None or score > best[0]:
            best = (score, nh, zin)
    _, nh, zin = best
    np.savetxt(os.path.join(HERE, "results", "315.csv"),
               np.column_stack([f / 1e6, 20 * np.log10(np.abs(dm.gamma(zin))),
                                zin.real, zin.imag]),
               delimiter=",", header="f_MHz,S11_dB,Re_Zin,Im_Zin", comments="")
    print(f"chosen loading coil: {nh} nH (results/315.csv written)")


if __name__ == "__main__":
    main()
