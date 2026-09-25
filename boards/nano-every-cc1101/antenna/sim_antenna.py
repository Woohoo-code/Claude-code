#!/usr/bin/env python3
"""openEMS FDTD model of the board's printed antennas.

The whole board is modelled: 100 x 100 x 1.6 mm FR4 (er 4.4, tan d 0.02),
solid copper on both layers over the ground region, and all four IFAs on
the top layer (so each antenna is tuned with its neighbours present). One
antenna is driven by a 50 ohm lumped port across its 1 mm feed gap; the
others' feed gaps are left open, as they are when their selector part is
not fitted.

Usage:  python sim_antenna.py <name> [tap tail] [outdir] [load_nH]
   name = 433 | 315 | 868 | 915   (defaults from antenna_geometry.PARAMS)
Prints Zin/S11 at the band centre; writes <outdir>/s11.csv.

Needs openEMS + CSXCAD Python bindings (https://openems.de).
"""

import math
import os
import sys
import tempfile

import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import EPS0, C0

from antenna_geometry import (BOARD, FREQ_MHZ, GND_X0, GND_X1, GND_Y0, NAMES, PARAMS,
                              TRACE_W, antenna, arm_parts, load, shorted)

ER, TAND, H = 4.4, 0.02, 1.6


def run(name, tap, tail, outdir, load_nh=None, two_port_exc=None):
    """two_port_exc = 1 or 2: model the loading-coil gap of `name` as a
    second 50 ohm port instead of an inductor, exciting port 1 (feed) or
    port 2 (coil gap). Returns the port objects' incident/reflected waves
    so the caller can build the 2-port S-matrix."""
    f0 = FREQ_MHZ[name] * 1e6
    fmin, fmax = 0.6 * f0, 1.4 * f0
    ants = {n: antenna(n, tap, tail) if n == name else antenna(n) for n in NAMES}

    fdtd = openEMS(NrTS=600000, EndCriteria=10 ** (-30 / 10))
    load_port = None
    fdtd.SetGaussExcite((fmin + fmax) / 2, (fmax - fmin) / 2)
    fdtd.SetBoundaryCond(["PML_8"] * 6)
    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(1e-3)

    fr4 = csx.AddMaterial("FR4", epsilon=ER, kappa=2 * np.pi * f0 * EPS0 * ER * TAND)
    fr4.AddBox([0, 0, 0], [BOARD, BOARD, H], priority=0)
    cu = csx.AddMetal("copper")
    for z in (0, H):
        cu.AddBox([GND_X0, GND_Y0, z], [GND_X1, BOARD, z], priority=10)

    w2 = TRACE_W / 2
    xs, ys = {0, BOARD, GND_X0, GND_X1}, {0, BOARD, GND_Y0}
    for n, a in ants.items():
        if not shorted(n):
            # short jumper not fitted: the leg stops 1 mm short of the ground edge
            (sx0, sy0), (sx1, sy1) = a["short"]
            if a["gap_axis"] == "x":
                d = 1.0 if sx1 > sx0 else -1.0
                a["short"] = [(sx0 + d, sy0), (sx1, sy1)]
            else:
                d = 1.0 if sy1 > sy0 else -1.0
                a["short"] = [(sx0, sy0 + d), (sx1, sy1)]
        pls = [("short", a["short"]), ("feed", a["feed"])]
        pls += [("arm", p) for p in (arm_parts(n, tap=tap, tail=tail) if n == name
                                     else arm_parts(n))]
        for key, pl in pls:
            for i, ((x1, y1), (x2, y2)) in enumerate(zip(pl, pl[1:])):
                lo = [min(x1, x2) - w2, min(y1, y2) - w2]
                hi = [max(x1, x2) + w2, max(y1, y2) + w2]
                if key == "feed" and i == 0:
                    # the feed end stops exactly at the gap, no end cap
                    if a["gap_axis"] == "y":
                        hi[1] = y1
                    elif x1 < x2:
                        lo[0] = x1
                    else:
                        hi[0] = x1
                if key == "arm":
                    # square ends only where the arm isn't cut for the inductor
                    ld = load(n)
                    if ld:
                        lx, ly = ld["at"]
                        for end in ((x1, y1), (x2, y2)):
                            if math.hypot(end[0] - lx, end[1] - ly) < 0.6:
                                if ld["axis"] == "y":
                                    lo[1], hi[1] = ((end[1], hi[1]) if end[1] > ly
                                                    else (lo[1], end[1]))
                                else:
                                    lo[0], hi[0] = ((end[0], hi[0]) if end[0] > lx
                                                    else (lo[0], end[0]))
                cu.AddBox([lo[0], lo[1], H], [hi[0], hi[1], H], priority=10)
                xs |= {lo[0], hi[0]}
                ys |= {lo[1], hi[1]}
        ld = load(n)
        if ld and n == name and two_port_exc:
            lx, ly = ld["at"]
            if ld["axis"] == "y":
                st, sp = [lx - w2, ly - 0.5, H], [lx + w2, ly + 0.5, H]
            else:
                st, sp = [lx - 0.5, ly - w2, H], [lx + 0.5, ly + w2, H]
            load_port = (st, sp, ld["axis"])
        elif ld:
            nh = ld["nh"] if (n != name or load_nh is None) else load_nh
            lx, ly = ld["at"]
            # pure inductor: openEMS's series R-L element went unstable here, so
            # the coil's loss (Q ~ 40) is accounted for analytically instead
            el = csx.AddLumpedElement(f"Lload{n}", ny="xy".index(ld["axis"]), caps=True,
                                      L=nh * 1e-9)
            if ld["axis"] == "y":
                el.AddBox([lx - w2, ly - 0.5, H], [lx + w2, ly + 0.5, H], priority=15)
            else:
                el.AddBox([lx - 0.5, ly - w2, H], [lx + 0.5, ly + w2, H], priority=15)

    a = ants[name]
    (gx, gy), (tx, ty) = a["feed_pt"], a["feed"][0]
    if a["gap_axis"] == "y":
        start, stop, d = [gx - w2, ty, H], [gx + w2, gy, H], "y"
    else:
        start, stop, d = [min(gx, tx), gy - w2, H], [max(gx, tx), gy + w2, H], "x"
    port = fdtd.AddLumpedPort(1, 50, start, stop, d, 1.0 if two_port_exc != 2 else 0,
                              priority=5)
    port2 = None
    if two_port_exc:
        st, sp, ax = load_port
        port2 = fdtd.AddLumpedPort(2, 50, st, sp, ax, 1.0 if two_port_exc == 2 else 0,
                                   priority=15)

    lam = C0 / fmax / 1e-3
    air = lam / 3
    mesh.AddLine("x", sorted(xs) + [-air, BOARD + air])
    mesh.AddLine("y", sorted(ys) + [-air, BOARD + air])
    mesh.AddLine("z", [0, H / 2, H, -air, H + air])
    for ax in "xy":   # merge lines closer than 0.5 mm (keeps the time step up)
        lines = sorted(set(round(v, 2) for v in mesh.GetLines(ax)))
        kept = [lines[0]]
        for v in lines[1:]:
            if v - kept[-1] >= 0.5:
                kept.append(v)
        mesh.ClearLines(ax)
        mesh.AddLine(ax, kept)
        mesh.SmoothMeshLines(ax, 3.0, 1.5)
    mesh.SmoothMeshLines("z", 3.0, 1.5)
    for ax in "xyz":
        mesh.SmoothMeshLines(ax, lam / 20, 1.4)

    os.makedirs(outdir, exist_ok=True)
    fdtd.Run(outdir, verbose=0, cleanup=True, numThreads=os.cpu_count())

    f = np.linspace(fmin, fmax, 1601)
    if two_port_exc:
        port.CalcPort(outdir, f)
        port2.CalcPort(outdir, f)
        return f, port, port2
    port.CalcPort(outdir, f)
    zin = port.uf_tot / port.if_tot
    s11 = port.uf_ref / port.uf_inc
    s11_db = 20 * np.log10(np.abs(s11))
    i0 = int(np.argmin(np.abs(f - f0)))
    np.savetxt(os.path.join(outdir, "s11.csv"),
               np.column_stack([f / 1e6, s11_db, zin.real, zin.imag]),
               delimiter=",", header="f_MHz,S11_dB,Re_Zin,Im_Zin", comments="")
    return {"name": name, "tap": tap, "tail": tail, "f0": f0, "z0": zin[i0],
            "s11_0": s11_db[i0], "fmin": f[int(np.argmin(s11_db))],
            "min_s11": float(np.min(s11_db))}


def two_port(name, tap, tail, outdir):
    """Run both excitations and save Z-parameters (feed = 1, coil gap = 2)."""
    s = np.zeros((2, 2, 1601), complex)
    for k in (1, 2):
        f, p1, p2 = run(name, tap, tail, os.path.join(outdir, f"exc{k}"), two_port_exc=k)
        inc = (p1 if k == 1 else p2).uf_inc
        s[0, k - 1] = p1.uf_ref / inc
        s[1, k - 1] = p2.uf_ref / inc
    eye = np.eye(2)
    z = np.array([50 * (eye + s[:, :, i]) @ np.linalg.inv(eye - s[:, :, i])
                  for i in range(s.shape[2])])
    np.savetxt(os.path.join(outdir, "z2port.csv"),
               np.column_stack([f / 1e6] + [v for a in range(2) for b in range(2)
                                            for v in (z[:, a, b].real, z[:, a, b].imag)]),
               delimiter=",", comments="",
               header="f_MHz,Z11r,Z11i,Z12r,Z12i,Z21r,Z21i,Z22r,Z22i")
    return f, z


if __name__ == "__main__":
    if sys.argv[1] == "--2port":
        name, tap, tail, out = sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
        two_port(name, tap, tail, out)
        print(f"{name} 2-port done -> {out}/z2port.csv", flush=True)
        sys.exit(0)
    name = sys.argv[1]
    tap = float(sys.argv[2]) if len(sys.argv) > 3 else PARAMS[name]["tap"]
    tail = float(sys.argv[3]) if len(sys.argv) > 3 else PARAMS[name]["tail"]
    out = sys.argv[4] if len(sys.argv) > 4 else tempfile.mkdtemp(prefix=f"ant{name}_")
    lnh = float(sys.argv[5]) if len(sys.argv) > 5 else None
    r = run(name, tap, tail, out, lnh)
    print(f"{r['name']} tap={r['tap']:.1f} tail={r['tail']:.1f} load={lnh}  "
          f"Zin({r['f0']/1e6:.2f})={r['z0'].real:.1f}{r['z0'].imag:+.1f}j  "
          f"S11={r['s11_0']:.1f}dB  minS11={r['min_s11']:.1f}dB@{r['fmin']/1e6:.1f}MHz",
          flush=True)
