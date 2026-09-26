import pcbnew, sys, math, collections
b = pcbnew.LoadBoard(sys.argv[1])
mm = pcbnew.ToMM
L = collections.Counter(); V = collections.Counter(); B = collections.Counter()
tot = hand = 0.0
for t in b.GetTracks():
    n = t.GetNetname()
    if t.GetClass() == "PCB_VIA":
        if not t.IsLocked() and n != "GND": V[n] += 1
        continue
    l = mm(t.GetLength())
    if t.IsLocked(): hand += l; continue
    L[n] += l; B[n] += 1; tot += l
print(f"autorouted: {tot:.1f} mm in {sum(B.values())} segments, {sum(V.values())} signal vias; hand-routed {hand:.1f} mm")
if len(sys.argv) > 2:
    for n in sorted(L, key=lambda k: -L[k]):
        print(f"  {n:10} {L[n]:6.1f} mm  {B[n]:3} segs  {V[n]} vias")
