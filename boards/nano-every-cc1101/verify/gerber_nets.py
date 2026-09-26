"""Netlist from the fab files alone: copper polygons from the Gerbers, joined
through every plated hole in the drill file, compared net by net with the
board's pads (shorts, opens), plus copper clearance, copper-to-edge,
annular rings, hole spacing, mask openings and paste, all measured on the
Gerbers against JLCPCB's published 2-layer limits."""
import sys, json, math, zipfile, io, os, tempfile, collections, itertools
import shapely
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
from shapely import affinity
from gerbonara.rs274x import GerberFile
from gerbonara.excellon import ExcellonFile
from gerbonara import graphic_primitives as gp
from gerbonara.utils import MM

LIM = dict(clear=0.10, edge=0.20, ring_pth=0.18, ring_pth_rec=0.25, via_ring=0.05, via_h2h=0.20, pad_h2h=0.45,
           mask_bridge=0.10, mask_to_trace=0.09)

def load(zp):
    z = zipfile.ZipFile(zp); d = tempfile.mkdtemp(); out = {}
    for n in z.namelist():
        p = os.path.join(d, n); open(p, "wb").write(z.read(n))
        ext = n.lower().rsplit(".", 1)[1]; out[ext] = p
    return out

def arc_pts(x1, y1, x2, y2, cx, cy, cw, n_per_rad=60):
    a1, a2 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    if cw:
        while a2 >= a1: a2 -= 2 * math.pi
    else:
        while a2 <= a1: a2 += 2 * math.pi
    if abs(math.hypot(x1 - x2, y1 - y2)) < 1e-9: a2 = a1 + (-2 * math.pi if cw else 2 * math.pi)
    r = math.hypot(x1 - cx, y1 - cy); n = max(4, int(abs(a2 - a1) * n_per_rad))
    return [(cx + r * math.cos(a1 + (a2 - a1) * i / n), cy + r * math.sin(a1 + (a2 - a1) * i / n)) for i in range(n + 1)]

def prim_geom(p):
    if isinstance(p, gp.Circle): return Point(p.x, p.y).buffer(p.r, 64)
    if isinstance(p, gp.Line): return LineString([(p.x1, p.y1), (p.x2, p.y2)]).buffer(p.width / 2, 32) if p.width > 0 else None
    if isinstance(p, gp.Arc): return LineString(arc_pts(p.x1, p.y1, p.x2, p.y2, p.cx, p.cy, p.clockwise)).buffer(p.width / 2, 32)
    if isinstance(p, gp.Rectangle):
        r = box(p.x - p.w / 2, p.y - p.h / 2, p.x + p.w / 2, p.y + p.h / 2)
        return affinity.rotate(r, p.rotation, origin=(p.x, p.y), use_radians=True) if p.rotation else r
    if isinstance(p, gp.ArcPoly):
        pts = []
        for (x1, y1), (x2, y2), (cw, (cx, cy)) in p.segments:
            if cw is None: pts.append((x1, y1))
            else: pts += arc_pts(x1, y1, x2, y2, cx, cy, cw)[:-1]
        g = Polygon(pts)
        return g if g.is_valid else g.buffer(0)
    raise TypeError(type(p))

def layer(path):
    """-> (union geometry, list of flashes (x, y, geom))"""
    g = GerberFile.open(path); dark, flashes = [], []
    from gerbonara.graphic_objects import Flash
    for obj in g.objects:
        geoms = [prim_geom(p) for p in obj.to_primitives(MM)]
        geoms = [x for x in geoms if x is not None and not x.is_empty]
        if not obj.polarity_dark: raise SystemExit(f"{path}: clear polarity not handled")
        dark += geoms
        if isinstance(obj, Flash): flashes.append((obj.x, obj.y, unary_union(geoms)))
    return unary_union(dark), flashes

def parts(geom):
    return list(geom.geoms) if hasattr(geom, "geoms") else [geom]

def main(zp, padsjson):
    f = load(zp); K = json.load(open(padsjson))
    edge_g = GerberFile.open(f["gm1"]); (ex0, ey0), (ex1, ey1) = edge_g.bounding_box(MM)
    # edge lines have width; the board outline is the centre line
    ew = min(o.aperture.equivalent_width(MM) for o in edge_g.objects)
    ex0, ey0, ex1, ey1 = ex0 + ew / 2, ey0 + ew / 2, ex1 - ew / 2, ey1 - ew / 2
    print(f"outline from .gm1: {ex1-ex0:.3f} x {ey1-ey0:.3f} mm")
    toB = lambda X, Y: (X - ex0, ey1 - Y)       # gerber -> board coords (y down)
    fromB = lambda x, y: (x + ex0, ey1 - y)
    top, top_fl = layer(f["gtl"]); bot, bot_fl = layer(f["gbl"])
    drl = ExcellonFile.open(f["drl"])
    holes = []
    for o in drl.drills():
        holes.append((o.x, o.y, o.tool.diameter if o.unit == MM else o.tool.diameter * 25.4))
    ok = True
    print(f"drill file: {len(holes)} plated holes, sizes {sorted({round(h[2], 3) for h in holes})}")
    T, Bt = parts(top), parts(bot)
    print(f"copper islands: top {len(T)}, bottom {len(Bt)}")
    # union-find over (layer, island)
    nodes = [("T", i) for i in range(len(T))] + [("B", i) for i in range(len(Bt))]
    par = {n: n for n in nodes}
    def find(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    def island(layer_parts, X, Y):
        pt = Point(X, Y); hits = [i for i, g in enumerate(layer_parts) if g.covers(pt)]
        return hits
    tree_T, tree_B = shapely.STRtree(T), shapely.STRtree(Bt)
    def isl(tree, lp, X, Y):
        pt = Point(X, Y); return [int(i) for i in tree.query(pt) if lp[int(i)].covers(pt)]
    unplated_copper = 0
    for X, Y, d in holes:
        t, b = isl(tree_T, T, X, Y), isl(tree_B, Bt, X, Y)
        if not t or not b:
            print(f"  hole at {toB(X, Y)} d={d}: copper top={bool(t)} bottom={bool(b)}"); unplated_copper += 1; ok = False; continue
        par[find(("T", t[0]))] = find(("B", b[0]))
    # map KiCad pads / vias onto islands
    items = [(f"{p['ref']}.{p['num']}", p["net"], p["x"], p["y"], p["top"], p["bot"]) for p in K["pads"] if not p["npth"] and (p["top"] or p["bot"])]
    items += [(f"via@{v['x']:.2f},{v['y']:.2f}", v["net"], v["x"], v["y"], True, True) for v in K["vias"]]
    comp_nets = collections.defaultdict(set); net_comps = collections.defaultdict(set); missing = []
    for name, net, x, y, ont, onb in items:
        X, Y = fromB(x, y); hit = None
        if ont:
            h = isl(tree_T, T, X, Y); hit = ("T", h[0]) if h else None
        if hit is None and onb:
            h = isl(tree_B, Bt, X, Y); hit = ("B", h[0]) if h else None
        if hit is None: missing.append(name); continue
        c = find(hit); key = net or f"<no net {name}>"
        comp_nets[c].add(key); net_comps[key].add(c)
    shorts = {c: n for c, n in comp_nets.items() if len(n) > 1}
    opens = {n: c for n, c in net_comps.items() if len(c) > 1}
    kic_nets = {p["net"] for p in K["pads"] if p["net"]}
    print(f"pads + vias located in the Gerber copper: {len(items) - len(missing)}/{len(items)}"
          + (f"  MISSING: {missing}" if missing else ""))
    print(f"nets: {len(kic_nets)} on the board, {len([n for n in net_comps if not n.startswith('<')])} found in the Gerbers")
    print(f"shorts (one copper island carrying >1 net): {len(shorts)}" + "".join(f"\n   {sorted(v)}" for v in shorts.values()))
    print(f"opens (one net split over >1 island): {len(opens)}" + "".join(f"\n   {k}: {len(v)} pieces" for k, v in opens.items()))
    ok &= not (shorts or opens or missing)
    # islands with no pad/via at all (floating copper)
    comps_all = {find(n) for n in nodes}
    floating = [c for c in comps_all if c not in comp_nets]
    fl_area = []
    for c in floating:
        a = sum((T if n[0] == "T" else Bt)[n[1]].area for n in nodes if find(n) == c); fl_area.append(a)
    print(f"floating copper islands (no pad or via): {len(floating)}" + (f", largest {max(fl_area):.3f} mm^2" if fl_area else ""))
    # clearance between different nets, per layer
    def min_clear(lp, name):
        tree = shapely.STRtree(lp); best = (9, None)
        for i, g in enumerate(lp):
            for j in tree.query(g.buffer(0.3)):
                j = int(j)
                if j <= i: continue
                ci, cj = find((name, i)), find((name, j))
                if ci == cj: continue
                dd = g.distance(lp[j])
                if dd < best[0]: best = (dd, (i, j))
        return best
    for name, lp in (("T", T), ("B", Bt)):
        d, ij = min_clear(lp, name)
        good = d >= LIM["clear"] - 1e-6; ok &= good
        where = ""
        if ij:
            p1, p2 = shapely.ops.nearest_points(lp[ij[0]], lp[ij[1]]); where = f" at {tuple(round(v, 2) for v in toB(p1.x, p1.y))}"
        print(f"{'top' if name == 'T' else 'bottom'} copper: smallest gap between different nets {d:.3f} mm{where} (JLCPCB min {LIM['clear']}) {'OK' if good else 'FAIL'}")
    # copper to board edge
    outline = box(ex0, ey0, ex1, ey1).exterior
    for name, g in (("top", top), ("bottom", bot)):
        close = []
        for pg in parts(g):
            dd = pg.distance(outline) if box(ex0, ey0, ex1, ey1).contains(pg.centroid) else 0
            if dd < LIM["edge"]:
                c = pg.centroid; close.append((round(dd, 3), tuple(round(v, 1) for v in toB(c.x, c.y)), round(pg.area, 2)))
        print(f"{name} copper closer than {LIM['edge']} mm to the edge: {len(close)} island(s) {sorted(close)[:6]}")
    # annular rings and hole spacing
    def ring(flashes, X, Y, d):
        best = None
        for fx, fy, g in flashes:
            if abs(fx - X) < 1e-3 and abs(fy - Y) < 1e-3:
                r = g.exterior.distance(Point(X, Y)) if g.geom_type == "Polygon" else min(q.exterior.distance(Point(X, Y)) for q in g.geoms)
                best = max(best or 0, r - d / 2)
        return best
    VXY = [(v["x"], v["y"]) for v in K["vias"]]
    isvia = lambda X, Y: any(abs(vx - toB(X, Y)[0]) < 0.02 and abs(vy - toB(X, Y)[1]) < 0.02 for vx, vy in VXY)
    VD = {(round(v["x"], 2), round(v["y"], 2)): v["d"] for v in K["vias"]}
    def via_flash(X, Y, g):     # a via's own flash (not a pad flashed at the same spot)
        if not isvia(X, Y): return False
        (x0, y0, x1, y1) = g.bounds; d = max(VD.values())
        return x1 - x0 <= d + 0.02 and y1 - y0 <= d + 0.02
    rings = collections.defaultdict(list)
    for X, Y, d in holes:
        kind = "via" if isvia(X, Y) else "pad"
        for nm, fl in (("top", top_fl), ("bottom", bot_fl)):
            r = ring(fl, X, Y, d)
            if r is None: print(f"  no pad flash at hole {toB(X, Y)} on {nm}"); ok = False; continue
            rings[kind].append(r)
    for kind, lim in (("via", LIM["via_ring"]), ("pad", LIM["ring_pth"])):
        mn = min(rings[kind]); good = mn >= lim - 1e-6; ok &= good
        print(f"annular ring, {kind}s: min {mn:.3f} mm over {len(rings[kind])//2} holes (limit {lim}"
              + (f", recommended {LIM['ring_pth_rec']}" if kind == 'pad' else "") + f") {'OK' if good else 'FAIL'}")
    h2h = {"via": 9, "pad": 9}
    for (X1, Y1, d1), (X2, Y2, d2) in itertools.combinations(holes, 2):
        g = math.hypot(X1 - X2, Y1 - Y2) - d1 / 2 - d2 / 2
        k1 = isvia(X1, Y1); k2 = isvia(X2, Y2)
        k = "via" if (k1 and k2) else "pad"
        h2h[k] = min(h2h[k], g)
    for k, lim in (("via", LIM["via_h2h"]), ("pad", LIM["pad_h2h"])):
        good = h2h[k] >= lim - 1e-6; ok &= good
        print(f"hole-to-hole ({'via-via' if k == 'via' else 'with a pad hole'}): min {h2h[k]:.3f} mm (limit {lim}) {'OK' if good else 'FAIL'}")

    # hole edge to copper of other nets (JLCPCB: via hole to track 0.2, PTH to track 0.28 / 0.35 recommended)
    worst = {"via": (9, None), "pad": (9, None)}
    for X, Y, d in holes:
        k = "via" if isvia(X, Y) else "pad"; hole = Point(X, Y).buffer(d / 2, 64)
        for nm, lp, tr in (("T", T, tree_T), ("B", Bt, tree_B)):
            own = isl(tr, lp, X, Y); own_c = find((nm, own[0])) if own else None
            for j in tr.query(hole.buffer(0.6)):
                j = int(j)
                if find((nm, j)) == own_c: continue
                dd = lp[j].distance(hole)
                if dd < worst[k][0]: worst[k] = (dd, toB(X, Y))
    for k, lim in (("via", 0.20), ("pad", 0.28)):
        dd, at = worst[k]; good = dd >= lim - 1e-6; ok &= good
        print(f"{k} hole edge to other-net copper: min {dd:.3f} mm at {tuple(round(v, 2) for v in at) if at else '-'} (limit {lim}) {'OK' if good else 'FAIL'}")
    # solder mask: every pad opened, every via tented, bridges
    for cu_fl, mk, lname in ((top_fl, "gts", "top"), (bot_fl, "gbs", "bottom")):
        mask, mfl = layer(f[mk]); mparts = parts(mask); mtree = shapely.STRtree(mparts)
        pad_fl = [(x, y, g) for x, y, g in cu_fl if not via_flash(x, y, g)]
        via_fl = [(x, y, g) for x, y, g in cu_fl if via_flash(x, y, g)]
        # pads the board deliberately keeps under mask (the CC1101 exposed pads: only
        # their paste windows are open, so the vias in them stay tented)
        masked = [(p["x"], p["y"]) for p in K["pads"] if (p["top"] if lname == "top" else p["bot"])
                  and not (p["fmask"] if lname == "top" else p["bmask"])]
        is_masked = lambda X, Y: any(abs(mx - toB(X, Y)[0]) < 0.02 and abs(my - toB(X, Y)[1]) < 0.02 for mx, my in masked)
        not_open = [toB(x, y) for x, y, g in pad_fl if not is_masked(x, y)
                    and not any(mparts[int(i)].covers(g.buffer(-0.001)) for i in mtree.query(g))]
        n_masked = sum(1 for x, y, g in pad_fl if is_masked(x, y))
        via_open = [toB(x, y) for x, y, g in via_fl if any(mparts[int(i)].intersects(g) for i in mtree.query(g))]
        # mask web between separate openings
        webs = []
        for i, g in enumerate(mparts):
            for j in mtree.query(g.buffer(0.5)):
                j = int(j)
                if j > i: webs.append((g.distance(mparts[j]), i, j))
        mw = min(webs)[0] if webs else 9
        for dd, i, j in sorted(webs)[:6]:
            if dd < LIM["mask_bridge"]:
                p1, p2 = shapely.ops.nearest_points(mparts[i], mparts[j]); print(f"    web {dd:.3f} mm at {tuple(round(v, 2) for v in toB(p1.x, p1.y))}")

        # openings must not expose copper of another net (JLCPCB: >= 0.09 mm from opening to neighbouring trace)
        cu = T if lname == "top" else Bt; cut = tree_T if lname == "top" else tree_B; nm = "T" if lname == "top" else "B"
        expo = []
        for g in mparts:
            owners = {find((nm, int(j))) for j in cut.query(g) if cu[int(j)].intersects(g.buffer(-0.001))}
            for j in cut.query(g.buffer(0.1)):
                j = int(j)
                if find((nm, j)) in owners: continue
                dd = cu[j].distance(g)
                if dd < LIM["mask_to_trace"]: c = g.centroid; expo.append((round(dd, 3), tuple(round(v, 2) for v in toB(c.x, c.y))))
        print(f"    openings closer than {LIM['mask_to_trace']} mm to another net's copper: {len(expo)} {sorted(expo)[:6]}")
        ok &= not expo
        print(f"    exposed vias at {[tuple(round(v, 2) for v in toB(x, y)) for x, y, g in via_fl if any(mparts[int(i)].intersects(g) for i in mtree.query(g))]}")
        good = not not_open and mw >= LIM["mask_bridge"] - 1e-6; ok &= good
        print(f"{lname} mask: {len(mparts)} openings; pad flashes not opened: {len(not_open)} {not_open[:4]} (+{n_masked} kept under mask by design); vias exposed: {len(via_open)}; "
              f"narrowest mask web {mw:.3f} mm (JLCPCB min bridge {LIM['mask_bridge']}) {'OK' if good else 'CHECK'}")
    # paste only on SMD pads
    paste, pfl = layer(f["gtp"]); pparts = parts(paste)
    smd = [p for p in K["pads"] if p["smd"] and p["top"]]; tht = [p for p in K["pads"] if p["drill"] > 0]
    def has_paste(p):
        X, Y = fromB(p["x"], p["y"]); c = Point(X, Y).buffer(max(p["sx"], p["sy"]) / 2)
        return any(q.intersects(c) for q in pparts)
    no_paste = [f"{p['ref']}.{p['num']}" for p in smd if not has_paste(p)]
    tht_paste = [f"{p['ref']}.{p['num']}" for p in tht if any(q.intersects(Point(*fromB(p['x'], p['y']))) for q in pparts)]
    print(f"paste: {len(pparts)} apertures; top SMD pads without paste: {len(no_paste)} {no_paste[:8]}; through-hole pads with paste: {len(tht_paste)} {tht_paste[:6]}")
    print("GERBER NETLIST + DFM: " + ("PASS" if ok else "FAIL"))
    return ok

if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
