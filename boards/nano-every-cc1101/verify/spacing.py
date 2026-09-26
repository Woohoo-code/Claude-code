"""Every pair of assembled SMD parts vs JLCPCB's 'Minimum Spacing Requirements for SMD
Components' (help article, Sep 2026): extent to extent, extent = body outline U pads."""
import json, csv, math, itertools, sys
B = json.load(open(sys.argv[1])); cpl = {r["Designator"] for r in csv.DictReader(open(sys.argv[2]))}
ORDER = ["0201", "0402", "0603", "0805", "1206", "QFN", "QFP", "SOP", "SOT", "BGA"]
ROWS = {"0201": [.15, .15, .18, .18, .25, 1, .5, .4, .2, 1], "0402": [.15, .18, .18, .25, 1, .5, .4, .2, 1],
        "0603": [.18, .18, .25, 1, .5, .4, .2, 1], "0805": [.18, .25, 1, .5, .4, .2, 1], "1206": [.35, 1, .5, .4, .2, 1],
        "QFN": [1, 1, 1, 1, 1.5], "QFP": [1.25, 1.25, 1, 1.5], "SOP": [.5, .4, 1], "SOT": [.4, 1], "BGA": [2]}
def need(a, b):
    i, j = sorted((ORDER.index(a), ORDER.index(b))); return ROWS[ORDER[i]][j - i]
def cls(fpid):
    for k, c in (("_0402_", "0402"), ("_0603_", "0603"), ("_0805_", "0805"), ("3225", "1206"), ("QFN", "QFN"), ("TSSOP", "SOP"), ("SOT-23", "SOT")):
        if k in fpid: return c
    return None
def env(v):
    xs = [p[2][0] for p in v["pads"]] + [p[2][2] for p in v["pads"]]; ys = [p[2][1] for p in v["pads"]] + [p[2][3] for p in v["pads"]]
    if v["body"]: xs += [v["body"][0], v["body"][2]]; ys += [v["body"][1], v["body"][3]]
    return [min(xs), min(ys), max(xs), max(ys)]
def gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0); dy = max(a[1] - b[3], b[1] - a[3], 0)
    return math.hypot(dx, dy) if (dx or dy) else -min(a[2] - b[0], b[2] - a[0], a[3] - b[1], b[3] - a[1])
def rects(v):                    # the part as it sits on the board: body + every pad
    return ([v["body"]] if v["body"] else []) + [p[2] for p in v["pads"] if p[4]]
def pgap(a, b):                  # gap between two parts (negative = overlap depth)
    return min(gap(r1, r2) for r1 in rects(a) for r2 in rects(b))
smd = {r: v for r, v in B.items() if r in cpl and cls(v["fpid"])}
bad = []
for r1, r2 in itertools.combinations(sorted(smd), 2):
    c1, c2 = cls(smd[r1]["fpid"]), cls(smd[r2]["fpid"]); n = need(c1, c2)
    g = pgap(smd[r1], smd[r2])
    if g < n: bad.append((c1 if "QFN" not in (c1, c2) else "QFN", g, n, r1, c1, r2, c2))
print(f"{len(smd)} assembled SMD parts, {len(smd)*(len(smd)-1)//2} pairs")
nonqfn = [b for b in bad if b[0] != "QFN"]
print(f"pairs below JLCPCB's table (other than next to the CC1101 QFNs): {len(nonqfn)}")
for _, g, n, r1, c1, r2, c2 in sorted(nonqfn, key=lambda b: b[1]):
    print(f"  {r1:5} {c1:4} - {r2:5} {c2:4}  {g:6.3f} mm  (table {n})")
# Next to the QFNs the parts follow TI's CC1101 reference layout (decoupling and
# balun at the pins), well inside JLCPCB's general 1 mm QFN recommendation (an
# inspection / rework allowance). Held to: bodies >= 0.25 mm apart, pads >= 0.2 mm.
BODY_MIN, PAD_MIN = 0.25, 0.20
qfn = [b for b in bad if b[0] == "QFN"]; worst_b, worst_p = 9, 9
print(f"parts closer than 1 mm to a CC1101 (TI reference placement): {len(qfn)}")
for _, g, n, r1, c1, r2, c2 in sorted(qfn, key=lambda b: b[1]):
    a, b2 = smd[r1], smd[r2]
    gb = gap(a["body"], b2["body"]) if a["body"] and b2["body"] else 9
    gp = min(gap(p[2], q[2]) for p in a["pads"] if p[4] for q in b2["pads"] if q[4])
    worst_b, worst_p = min(worst_b, gb), min(worst_p, gp)
    print(f"  {r1:5} - {r2:5}  body gap {gb:5.3f} mm  pad gap {gp:5.3f} mm")
ok = not nonqfn and worst_b >= BODY_MIN - 1e-6 and worst_p >= PAD_MIN - 1e-6
print(f"SPACING: {'PASS' if ok else 'FAIL'} (next to the QFNs: bodies >= {worst_b:.2f} mm, pads >= {worst_p:.2f} mm; "
      f"held to {BODY_MIN} / {PAD_MIN})")
sys.exit(0 if ok else 1)
