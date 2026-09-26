"""Fit JLCPCB's (EasyEDA) footprint of every assembled part onto the board's
pads, giving the exact Mid X / Mid Y / Rotation JLCPCB needs, and check the
footprint matches (pad count, pitch, polarity)."""
import json, sys, csv, math, numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import ez
FP = json.load(open(sys.argv[1])); BOM = sys.argv[2]; H = float(sys.argv[3]); OUT = sys.argv[4]
CMP = sys.argv[5] if len(sys.argv) > 5 else None
lcsc = {}
for r in csv.DictReader(open(BOM)):
    for d in r["Designator"].split(","): lcsc[d.strip()] = r["LCSC Part #"]
# Nano sockets: pads of the Nano footprint's two rows
a1 = FP["A1"]
for ref, rng in (("S1", range(1, 16)), ("S2", range(16, 31))):
    pads = [[str(int(p[0]) - rng[0] + 1)] + p[1:] for p in a1["pads"] if int(p[0]) in rng]
    FP[ref] = dict(fpid="socket", value="1x15 socket", pads=pads,
                   x=np.mean([p[1] for p in pads]), y=np.mean([p[2] for p in pads]), rot=0)
KICAD_LED_K = "1"                                   # KiCad LED_SMD: pad 1 = cathode
def rot(v, th):
    c, s = math.cos(math.radians(th)), math.sin(math.radians(th)); return np.array([c*v[0]-s*v[1], s*v[0]+c*v[1]])
rows, report = [], []
for ref in sorted(lcsc, key=lambda r: (r.rstrip("0123456789"), int(''.join(ch for ch in r if ch.isdigit()) or 0))):
    code = lcsc[ref]; e = ez.pads(code); k = FP[ref]
    # top-side pads only (SMA has bottom ground legs), y-up coordinates
    E = [(p["num"], np.array([p["x"], -p["y"]])) for p in e["pads"] if p["layer"] in ("1", "11")]
    K = [(p[0], np.array([p[1], -p[2]])) for p in k["pads"] if p[3]]
    names = e["names"]
    # pad-number correspondence (polarity): LED maps by A/K names
    if "LED" in k["fpid"]:
        kn = {KICAD_LED_K: [n for n, v in names.items() if v.upper().startswith("K")][0],
              [p[0] for p in K if p[0] != KICAD_LED_K][0]: [n for n, v in names.items() if v.upper().startswith("A")][0]}
    else:
        kn = {n: n for n, _ in K}
    best = None
    for th in (0, 90, 180, 270):
        Er = [(n, rot(v, th)) for n, v in E]
        pairs = []
        if len(E) == len(K) and all(kn.get(n) in dict(E) for n, _ in K) and "SMA" not in k["fpid"]:
            ed = dict(Er); pairs = [(kv, ed[kn[n]]) for n, kv in K]
        else:                                           # geometric (unnumbered / different numbering)
            kc = np.mean([v for _, v in K], axis=0); ec = np.mean([v for _, v in Er], axis=0)
            for n, kv in K:
                j = min(Er, key=lambda t: np.linalg.norm((t[1] - ec) - (kv - kc)))
                pairs.append((kv, j[1]))
        # translation: centre of the pad-centre bounding boxes (exact for pads that
        # are symmetric but spaced differently, e.g. SOT-23 IPC vs vendor)
        kb = np.array([kv for kv, _ in pairs]); eb = np.array([ev for _, ev in pairs])
        t = (kb.min(0) + kb.max(0)) / 2 - (eb.min(0) + eb.max(0)) / 2
        err = max(np.linalg.norm(kv - (ev + t)) for kv, ev in pairs)
        score = err
        if "SMA" in k["fpid"]:                          # body must point off the board edge (+x local)
            body = np.mean([np.array([x, -y]) for x, y in e["body"]], axis=0) if e["body"] else np.zeros(2)
            pc = np.mean([v for _, v in E], axis=0)
            dirv = rot(body - pc, th); want = rot(np.array([1.0, 0.0]), k["rot"])
            score += 0 if np.dot(dirv, want) > 0 else 100
        if best is None or score < best[0] - 1e-6:
            best = (score, th, t, err)
    score, th, t, err = best
    X, Y = t[0], t[1] + H
    old = None
    rows.append([ref, f"{X:.3f}mm", f"{Y:.3f}mm", "Top", f"{th:.0f}"])
    report.append((ref, code, e["package"], len(E), len(K), err, th, X, Y, k["rot"]))
with open(OUT, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]); w.writerows(rows)
bad = [r for r in report if r[5] > 0.35 or r[3] != r[4]]
for r in report:
    flag = ("  <-- PAD COUNT DIFFERS" if r[3] != r[4] else
            "  (vendor pad shape differs: same pins, centre, rotation)" if r[5] > 0.1 else "")
    print(f"{r[0]:5} {r[1]:9} {r[2][:34]:34} pads {r[3]:2}/{r[4]:2}  fit err {r[5]:.3f} mm  rot {r[6]:3.0f} (KiCad {r[9]:3.0f})  at ({r[7]:.2f}, {r[8]:.2f}){flag}")
print(f"{len(report)} parts fitted, {len(bad)} to check")

if CMP:                                              # check the fab CPL against the fit
    got = {r["Designator"]: r for r in csv.DictReader(open(CMP))}
    fit = {r[0]: r for r in rows}
    sym180 = lambda ref, fpid: ref[0] in "RCLY" or "Pin" in fpid or ref.startswith("S")
    errs = []
    for ref, r in fit.items():
        if ref not in got: errs.append(f"{ref}: missing from CPL"); continue
        g = got[ref]
        dx = float(g["Mid X"][:-2]) - float(r[1][:-2]); dy = float(g["Mid Y"][:-2]) - float(r[2][:-2])
        dr = (float(g["Rotation"]) - float(r[4])) % 360
        okrot = dr == 0 or (dr == 180 and sym180(ref, FP[ref]["fpid"])) or ref.startswith("AE")
        if math.hypot(dx, dy) > 0.05 or not okrot:
            errs.append(f"{ref}: CPL ({g['Mid X']}, {g['Mid Y']}, {g['Rotation']}) vs fit ({r[1]}, {r[2]}, {r[4]})")
    extra = sorted(set(got) - set(fit))
    if extra: errs.append(f"in CPL but not in BOM: {extra}")
    print("CPL vs JLCPCB footprint fit: " + ("ALL %d PARTS MATCH" % len(fit) if not errs else "MISMATCH\n  " + "\n  ".join(errs)))
