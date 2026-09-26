"""Nodal (MNA-style) simulation of the antenna feed networks, built from the
actual copper of the routed board: every track segment is a lossy CPWG
transmission line (Z0/eps_eff from the 2-D field solver), 0R links are
0.03 ohm + 0.5 nH, empty pads 0.1 pF to ground, the selected coil a 50 ohm
load where its feed leaves the ground pour (x = 62.8 mm)."""
import numpy as np, json, math, sys, collections
C0, MU0 = 2.998e8, 4e-7 * np.pi
import os
TAB = {float(k): v for k, v in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cpwg_table.json"))).items()}
def z0eps(w):
    ws = sorted(TAB); w = min(max(w, ws[0]), ws[-1])
    for a, b in zip(ws, ws[1:]):
        if a <= w <= b:
            t = (w - a) / (b - a) if b > a else 0
            return tuple(TAB[a][i] + t * (TAB[b][i] - TAB[a][i]) for i in (0, 1))
    return TAB[ws[-1]]
GEO = json.load(open(sys.argv[1]))
POUR_X = 62.8
def build(radio, selected):
    nets = {"A": ["ANT_A", "M_433", "FEED_433", "M_315", "FEED_315", "SMA_A"],
            "B": ["ANT_B", "M_868", "FEED_868", "M_915", "FEED_915", "SMA_B"]}[radio]
    src = ("C125" if radio == "A" else "C625", "2")
    segs = [[n, tuple(a), tuple(b), w] for n, a, b, w in GEO["segs"] if n in nets]
    pads = {(r, num): (net, tuple(c), tuple(bb), v) for r, num, net, c, bb, v in GEO["pads"] if net in nets}
    # clip feed lines at the pour edge: beyond it the copper belongs to the antenna
    clipped = []
    for net, a, b, w in segs:
        if net.startswith("FEED"):
            if a[0] > POUR_X and b[0] > POUR_X: continue
            if b[0] > POUR_X: b = (POUR_X, a[1] + (b[1] - a[1]) * (POUR_X - a[0]) / (b[0] - a[0]))
            if a[0] > POUR_X: a = (POUR_X, b[1] + (a[1] - b[1]) * (POUR_X - b[0]) / (a[0] - b[0]))
        clipped.append([net, a, b, w])
    segs = clipped
    # nodes: split every segment at points of the same net lying on it
    key = lambda p: (round(p[0], 3), round(p[1], 3))
    pts = collections.defaultdict(set)
    for net, a, b, w in segs: pts[net] |= {key(a), key(b)}
    for (ref, num), (net, c, bb, v) in pads.items(): pts[net].add(key(c))
    lines = []
    for net, a, b, w in segs:
        L = math.dist(a, b)
        if L < 1e-6: continue
        on = [p for p in pts[net] if abs((p[0]-a[0])*(b[1]-a[1]) - (p[1]-a[1])*(b[0]-a[0])) / L < 2e-3
              and -1e-3 <= ((p[0]-a[0])*(b[0]-a[0]) + (p[1]-a[1])*(b[1]-a[1])) / L <= L + 1e-3]
        on.sort(key=lambda p: math.dist(a, p))
        for p, q in zip(on, on[1:]):
            if math.dist(p, q) > 1e-4: lines.append((net, p, q, w))
    # a track end inside a pad joins that pad's node
    node = {}
    def nid(net, p):
        for (ref, num), (pn, c, (x0, y0, x1, y1), v) in pads.items():
            if pn == net and x0 - 1e-3 <= p[0] <= x1 + 1e-3 and y0 - 1e-3 <= p[1] <= y1 + 1e-3:
                p = key(c); break
        return node.setdefault((net, p), len(node))
    elems = [("tl", nid(n, p), nid(n, q), math.dist(p, q) * 1e-3, w) for n, p, q, w in lines]
    padnode = {k: nid(v[0], key(v[1])) for k, v in pads.items()}
    # components between nets
    byref = collections.defaultdict(list)
    for (ref, num), v in pads.items(): byref[ref].append((num, v))
    load = None
    for ref, lst in byref.items():
        val = lst[0][1][3]
        if ref.startswith("AE"):
            band = lst[0][1][0].split("_")[1]
            if band == selected:                    # load at the pour-edge end of its feed
                feed = [e for e in elems if e[0] == "tl"]
                fnodes = [n for (net, p), n in node.items() if net == f"FEED_{band}" and abs(p[0] - POUR_X) < 1e-3]
                load = fnodes[0]
            continue
        if ref.startswith("J"):                     # SMA jack pad: small open stub
            elems.append(("c", padnode[(ref, lst[0][0])], None, 0.2e-12)); continue
        SEL = {"433": "R301", "315": "R311", "868": "R321", "915": "R331"}
        if ref in SEL.values():                     # the band under test is selected
            val = "0R" if ref == SEL[selected] else "DNP"
        if len(lst) == 2:
            n1, n2 = padnode[(ref, lst[0][0])], padnode[(ref, lst[1][0])]
            if val.startswith("DNP"):
                elems += [("c", n1, None, 0.1e-12), ("c", n2, None, 0.1e-12)]
            elif val == "0R":
                elems.append(("z", n1, n2, (0.03, 0.5e-9)))
        elif len(lst) == 1:                         # pad of a part whose other pad is GND / another net
            n1 = padnode[(ref, lst[0][0])]
            elems.append(("c", n1, None, 0.1e-12) if val.startswith("DNP") else ("z0", n1, None, 0))
    return elems, len(node), padnode[src], load

def solve(elems, n, src, load, f, rl=50.0, rs=50.0):
    w = 2 * np.pi * f; Y = np.zeros((n, n), complex)
    for e in elems:
        if e[0] == "tl":
            _, a, b, L, wd = e; z0, ee = z0eps(wd)
            q = (ee - 1) / (4.5 - 1)
            ad = np.pi * f * 4.5 * q * 0.02 / (C0 * np.sqrt(ee))
            ac = np.sqrt(np.pi * f * MU0 / 5.8e7) / (z0 * wd * 1e-3)
            g = ad + ac + 1j * w * np.sqrt(ee) / C0
            y11, y12 = 1 / (z0 * np.tanh(g * L)), -1 / (z0 * np.sinh(g * L))
            Y[a, a] += y11; Y[b, b] += y11; Y[a, b] += y12; Y[b, a] += y12
        elif e[0] == "z":
            _, a, b, (r, l) = e; y = 1 / (r + 1j * w * l)
            Y[a, a] += y; Y[b, b] += y; Y[a, b] -= y; Y[b, a] -= y
        elif e[0] == "c":
            Y[e[1], e[1]] += 1j * w * e[3]
    Y += np.eye(n) * 1e-12                      # leak: floating (unselected) sub-nets
    Y[load, load] += 1 / rl
    Yin = Y.copy(); Yin[src, src] += 1 / rs
    I = np.zeros(n, complex); I[src] = 1 / rs                  # 1 V source behind rs (Norton)
    V = np.linalg.solve(Yin, I)
    Iz = np.zeros(n, complex); Iz[src] = 1.0
    Zin = np.linalg.solve(Y + np.eye(n) * 1e-15, Iz)[src]
    s11 = (Zin - rs) / (Zin + rs)
    p_load = abs(V[load]) ** 2 / (2 * rl); p_av = 1 / (8 * rs)
    return Zin, 20 * np.log10(abs(s11)), p_load / p_av

if __name__ == "__main__":
    cases = [("A", "433", [433.05, 433.92, 434.79]), ("A", "315", [314.5, 315.0, 315.5]),
             ("B", "868", [863.0, 868.3, 870.0]), ("B", "915", [902.0, 915.0, 928.0])]
    print("balun output -> selected coil (50 ohm), board copper + parts as built")
    for radio, band, fs in cases:
        elems, n, src, load = build(radio, band)
        # the selector of the band under test is fitted, the other one empty
        for i, e in enumerate(elems):
            pass
        for f in fs:
            zin, s11, g = solve(elems, n, src, load, f * 1e6)
            print(f"  radio {radio} -> {band} coil @ {f:7.2f} MHz: Zin {zin.real:5.1f}{zin.imag:+6.1f}j ohm  "
                  f"S11 {s11:6.1f} dB  power to coil {g*100:5.1f} %")
