#!/usr/bin/env python3
"""Tune every printed antenna to any frequency the CC1101 supports.

Each antenna has a series tuning element in its arm (0 ohm / inductor /
capacitor) and a T-match at its feed. sim_antenna.py --2port gives each
antenna's 2-port Z-parameters (port 1 = feed, port 2 = tuning gap), so for
any tuning element Z_t the feed impedance is exactly

    Zin = Z11 - Z12 * Z21 / (Z22 + Z_t)

For every MHz in each antenna's range this picks the tuning element and
T-match (standard E12/E24 0603 parts, with realistic loss: inductor Q 40,
capacitor Q 300, 0 ohm link 0.6 nH) that deliver the most power into the
antenna with |S11| < -10 dB.

Writes:
  results/tuning_<band>.csv   every MHz: part values, S11, efficiency
  results/tuning.md           condensed table (every 5 MHz + ISM centres)
  results/tuning.png          achievable S11 / efficiency across each range
  match.py                    the board's default fit (DEFAULT_MHZ below), from
                              JLCPCB fee-free 0603 values only (CHEAP_*)
"""

import csv
import math
import os

import numpy as np

from antenna_geometry import NAMES, TUNE_RANGE

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
Z0 = 50.0
Q_L, Q_C = 40.0, 300.0
E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3,
       4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]
E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
CAPS = sorted({round(v * 10 ** d, 2) for v in E24 for d in (-1, 0, 1, 2)
               if 0.5 <= v * 10 ** d <= 100})                # pF
INDS = sorted({round(v * 10 ** d, 1) for v in E12 for d in (0, 1, 2)
               if 1.0 <= v * 10 ** d <= 270})                # nH
# JLCPCB basic / preferred-extended 0603 parts (no per-part-type fee): the
# board's default fits use only these, the per-MHz tables use full E24/E12.
CHEAP_CAPS = [3.0, 4.7, 6.0, 6.8, 8.2, 10, 12, 15, 18, 20, 22, 27, 30, 33, 47, 56, 68, 100]
CHEAP_INDS = [39.0]   # LQW18AN39NG00D wire-wound (extended; the fee-free 68 nH is Q~12)
DEFAULT_MHZ = {"433": 433.92, "315": 315.0, "868": 868.3, "915": 915.0}
DEFAULT_FITTED = {"433", "868"}          # radio A ships on 433, radio B on 868
REFS = {"433": ("R301", "C301", "L301", "L401"), "315": ("R311", "C311", "L311", "L402"),
        "868": ("R321", "C321", "L321", "L404"), "915": ("R331", "C331", "L331", "L405")}
ISM = {"315": [315.0], "433": [433.92], "868": [868.3], "915": [915.0]}


def load_z(name):
    rows = list(csv.reader(open(os.path.join(RES, f"{name}_z2port.csv"))))[1:]
    a = np.array([[float(v) for v in r] for r in rows])
    z = [a[:, 1 + 2 * i] + 1j * a[:, 2 + 2 * i] for i in range(4)]
    return a[:, 0] * 1e6, z


def zpart(part, f):
    kind, val = part
    w = 2 * np.pi * f
    if kind == "0R":
        return 0.05 + 1j * w * 0.6e-9
    if kind == "L":
        x = w * val * 1e-9
        return x / Q_L + 1j * x
    x = 1 / (w * val * 1e-12)
    return x / Q_C - 1j * x


def label(part):
    kind, val = part
    return "0R" if kind == "0R" else (f"{val:g}nH" if kind == "L" else f"{val:g}pF")


def nearest(values, v):
    i = int(np.argmin([abs(math.log(x / v)) for x in values]))
    return [values[j] for j in range(max(0, i - 1), min(len(values), i + 2))]


def series_parts(x, w, caps=CAPS, inds=INDS):
    """Candidate parts realising series reactance x at angular frequency w."""
    if abs(x) < 3:
        return [("0R", 0)]
    if x > 0:
        return [("L", v) for v in nearest(inds, x / w * 1e9)] + [("0R", 0)]
    return [("C", v) for v in nearest(caps, 1 / (w * -x) * 1e12)] + [("0R", 0)]


def shunt_parts(b, w, caps=CAPS, inds=INDS):
    if b > 0:
        return [("C", v) for v in nearest(caps, b / w * 1e12)]
    return [("L", v) for v in nearest(inds, 1 / (w * -b) * 1e9)]


def evaluate(zl, f, s1, sh, s2):
    """Return (|gamma|, fraction of input power reaching zl)."""
    z2 = zl + zpart(s2, f)
    ysh = 1 / zpart(sh, f)
    zm = 1 / (1 / z2 + ysh)
    zin = zm + zpart(s1, f)
    g = abs((zin - Z0) / (zin + Z0))
    i1 = 1 / zin
    vm = 1 - i1 * zpart(s1, f)
    i2 = vm / z2
    eff = (abs(i2) ** 2 * zl.real) / np.real(1 / np.conj(zin))
    return g, float(eff)


def l_match(zl, f, caps=CAPS, inds=INDS):
    """Analytic L-sections (both orientations), snapped to real parts."""
    w = 2 * np.pi * f
    r, x = zl.real, zl.imag
    cands = []
    if 0 < r < Z0:                       # shunt at the node, series S2 at the load
        for sgn in (1, -1):
            xp = sgn * math.sqrt(Z0 * r - r * r)
            b = -(1 / complex(r, xp)).imag
            for s2 in series_parts(xp - x, w, caps, inds):
                for sh in shunt_parts(b, w, caps, inds):
                    cands.append((("0R", 0), sh, s2))
    y = 1 / zl
    g = y.real
    if 0 < g < 1 / Z0:                   # shunt at the load, series S1 at the node
        for sgn in (1, -1):
            bt = sgn * math.sqrt(g / Z0 - g * g)
            x1 = -(1 / complex(g, bt)).imag
            for sh in shunt_parts(bt - y.imag, w, caps, inds):
                for s1 in series_parts(x1, w, caps, inds):
                    cands.append((s1, sh, ("0R", 0)))
    return cands


def best_at(z, f_all, ft, caps=CAPS, inds=INDS):
    i = int(np.argmin(np.abs(f_all - ft)))
    f = f_all[i]
    z11, z12, z21, z22 = (v[i] for v in z)
    best = None
    tune_opts = [("0R", 0)] + [("L", v) for v in inds] + [("C", v) for v in caps]
    for tp in tune_opts:
        zt = zpart(tp, f)
        zin = z11 - z12 * z21 / (z22 + zt)
        if zin.real <= 0.2:
            continue
        i2 = -z21 / (z22 + zt)
        eff_t = 1 - abs(i2) ** 2 * zt.real / zin.real
        if eff_t <= 0:
            continue
        for s1, sh, s2 in l_match(zin, f, caps, inds):
            gm, eff_m = evaluate(zin, f, s1, sh, s2)
            total = eff_t * eff_m * (1 - gm ** 2)
            simpler = 0.005 * sum(p[0] == "0R" for p in (tp, s1, sh, s2))
            score = (total if gm < 10 ** (-10 / 20) else total - 1) + simpler
            if best is None or score > best[0]:
                best = (score, tp, s1, sh, s2, gm, eff_t * eff_m)
    _, tp, s1, sh, s2, gm, eff = best
    return {"f": ft, "tune": tp, "s1": s1, "sh": sh, "s2": s2,
            "s11": 20 * math.log10(max(gm, 1e-6)), "eff": eff}


def main():
    table = {}
    for n in NAMES:
        f_all, z = load_z(n)
        lo, hi = TUNE_RANGE[n]
        freqs = sorted(set(np.arange(lo, hi + 1, 1.0).tolist() + ISM[n]))
        rows = [best_at(z, f_all, ft * 1e6) for ft in freqs]
        table[n] = rows
        with open(os.path.join(RES, f"tuning_{n}.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["f_MHz", f"tune {REFS[n][3]}", f"S1 {REFS[n][0]}",
                        f"shunt {REFS[n][1]}", f"S2 {REFS[n][2]}", "S11_dB",
                        "power_to_antenna_pct"])
            for r in rows:
                w.writerow([f"{r['f'] / 1e6:g}", label(r["tune"]), label(r["s1"]),
                            label(r["sh"]), label(r["s2"]), f"{r['s11']:.1f}",
                            f"{r['eff'] * 100:.0f}"])
        worst = max(r["s11"] for r in rows)
        print(f"{n}: {lo}-{hi} MHz, worst S11 {worst:.1f} dB, efficiency "
              f"{min(r['eff'] for r in rows) * 100:.0f}-{max(r['eff'] for r in rows) * 100:.0f} %")

    md = ["# Antenna tuning for every CC1101 frequency", "",
          "Pick your frequency, fit the four parts on that row (all 0603), fit the",
          "antenna's selector, and the antenna is resonant and matched there. The",
          "full per-MHz tables are `tuning_<band>.csv`. The **power to antenna** figure",
          "is the share of the radio's output left after the tuning and match parts'",
          "losses (radiation efficiency of the antenna itself not included).", ""]
    for n in NAMES:
        lo, hi = TUNE_RANGE[n]
        r0, r1, r2, r3 = REFS[n]
        md += [f"## {n} MHz antenna: {lo}-{hi} MHz", "",
               f"| MHz | tune {r3} | S1 {r0} | shunt {r1} | S2 {r2} | S11 | power to antenna |",
               "|---|---|---|---|---|---|---|"]
        for r in table[n]:
            fm = r["f"] / 1e6
            if abs(fm % 5) < 1e-6 or fm in ISM[n]:
                md.append(f"| {fm:g} | {label(r['tune'])} | {label(r['s1'])} | "
                          f"{label(r['sh'])} | {label(r['s2'])} | {r['s11']:.1f} dB | "
                          f"{r['eff'] * 100:.0f} % |")
        md.append("")
    md += ["Radio A needs the 315 MHz front-end BOM for 300-348 MHz and the 433 MHz",
           "BOM for 387-464 MHz; radio B's 868/915 front end covers 779-928 MHz.", "",
           "## External whip (SMA J1/J2 or wire in H1/H2): any frequency", "",
           "Fit R403 (radio A) or R406 (radio B) instead of a printed-antenna selector.",
           "A quarter-wave whip over the board's ground plane is about",
           "**L (mm) = 71 250 / f (MHz)** (0.95 x lambda/4). A telescopic SMA whip set",
           "to this length, or a wire soldered into H1/H2 and cut to it, works at every",
           "CC1101 frequency.", "",
           "| MHz | whip (mm) | MHz | whip (mm) | MHz | whip (mm) |",
           "|---|---|---|---|---|---|"]
    lows = list(range(300, 350, 5)) + [348]
    mids = list(range(390, 465, 5)) + [387, 433.92, 464]
    highs = list(range(780, 930, 10)) + [779, 868.3, 915, 928]
    cols = [sorted(set(lows)), sorted(set(mids)), sorted(set(highs))]
    for i in range(max(map(len, cols))):
        cells = []
        for c in cols:
            if i < len(c):
                cells += [f"{c[i]:g}", f"{71250 / c[i]:.0f}"]
            else:
                cells += ["", ""]
        md.append("| " + " | ".join(cells) + " |")
    md.append("")
    open(os.path.join(RES, "tuning.md"), "w").write("\n".join(md))

    # board defaults
    lines = ['"""Default part values per antenna, generated by tune.py (do not edit).',
             "", "Branch: S1 (series, selector) -> C (shunt) -> S2 (series) -> antenna,",
             'plus "tune" = the series element in the antenna arm. Other frequencies:',
             'see results/tuning.md.', '"""', "", "MATCH = {"]
    for n in NAMES:
        f_all, z = load_z(n)
        r = best_at(z, f_all, DEFAULT_MHZ[n] * 1e6, CHEAP_CAPS, CHEAP_INDS)
        full = min(table[n], key=lambda r: abs(r["f"] / 1e6 - DEFAULT_MHZ[n]))
        print(f"default {n} @ {DEFAULT_MHZ[n]} MHz, fee-free parts: S11 {r['s11']:.1f} dB, "
              f"{r['eff'] * 100:.0f} % (any E24 part: {full['s11']:.1f} dB, "
              f"{full['eff'] * 100:.0f} %)")
        s1 = label(r["s1"])
        sel = s1 if n in DEFAULT_FITTED else f"DNP ({s1} to use)"
        tune = label(r["tune"])
        if n not in DEFAULT_FITTED and r["tune"][0] == "L":
            tune = f"DNP ({tune} to use)"     # extended part: fit by hand when needed
        lines.append(f'    "{n}": {{"refs": {REFS[n][:3]!r}, "tune_ref": "{REFS[n][3]}", '
                     f'"s1": {sel!r}, "c": {label(r["sh"])!r}, "s2": {label(r["s2"])!r}, '
                     f'"tune": {tune!r}, "f_mhz": {DEFAULT_MHZ[n]}, '
                     f'"s11_db": {r["s11"]:.1f}, "eff_pct": {r["eff"] * 100:.0f}}},')
    lines.append("}")
    open(os.path.join(HERE, "match.py"), "w").write("\n".join(lines) + "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True)
    for n, c in zip(NAMES, ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]):
        fm = [r["f"] / 1e6 for r in table[n]]
        a1.plot(fm, [r["s11"] for r in table[n]], color=c, label=f"{n} MHz antenna")
        a2.plot(fm, [r["eff"] * 100 for r in table[n]], color=c)
    a1.axhline(-10, color="gray", ls="--", lw=0.8)
    a1.set_ylabel("S11 when tuned (dB)")
    a1.set_ylim(-40, 0)
    a1.legend(ncol=4, fontsize=8)
    a1.set_title("Every CC1101 frequency: best tuning-part + T-match fit per MHz")
    a2.set_ylabel("power to antenna (%)")
    a2.set_ylim(0, 100)
    a2.set_xlabel("MHz")
    for ax in (a1, a2):
        ax.grid(alpha=0.3)
        for lo, hi in ((300, 348), (387, 464), (779, 928)):
            ax.axvspan(lo, hi, color="gray", alpha=0.07)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "tuning.png"), dpi=110)


if __name__ == "__main__":
    main()
