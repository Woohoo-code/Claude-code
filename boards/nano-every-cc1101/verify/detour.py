import pcbnew, sys, math, collections
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
pads = collections.defaultdict(list)
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname(): pads[p.GetNetname()].append((mm(p.GetPosition().x), mm(p.GetPosition().y), f"{fp.GetReference()}.{p.GetNumber()}"))
length = collections.Counter(); vias = collections.Counter()
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA": vias[t.GetNetname()] += 1
    else: length[t.GetNetname()] += mm(t.GetLength())
def mst(pts):
    if len(pts) < 2: return 0
    inT = {0}; tot = 0
    d = {i: math.dist(pts[0][:2], pts[i][:2]) for i in range(1, len(pts))}
    while d:
        j = min(d, key=d.get); tot += d.pop(j); inT.add(j)
        for k in d: d[k] = min(d[k], math.dist(pts[j][:2], pts[k][:2]))
    return tot
rows = []
for n, pts in pads.items():
    if n in ("GND",) or n.startswith("unconnected"): continue
    m = mst(pts); L = length[n]
    if m > 0 and L > 0: rows.append((L / m, n, L, m, vias[n], len(pts)))
rows.sort(reverse=True)
print(f"{'net':12} {'routed':>7} {'direct':>7} {'ratio':>5} vias pads")
for r, n, L, m, v, k in rows[:int(sys.argv[2]) if len(sys.argv) > 2 else 60]:
    print(f"{n:12} {L:7.1f} {m:7.1f} {r:5.2f} {v:4} {k:4}")
tot_L = sum(r[2] for r in rows); tot_m = sum(r[3] for r in rows)
print(f"TOTAL signal/power copper {tot_L:.0f} mm vs straight-line minimum {tot_m:.0f} mm (x{tot_L/tot_m:.2f})")
