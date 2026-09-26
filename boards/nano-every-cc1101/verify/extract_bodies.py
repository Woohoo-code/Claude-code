# Per footprint: F.Fab body outline (line centres, i.e. without the stroke width), pads, placement.
import pcbnew, json, sys
B = pcbnew.LoadBoard(sys.argv[1]); mm = lambda v: pcbnew.ToMM(v) - 100
out = {}
for fp in B.GetFootprints():
    xs, ys = [], []
    for g in fp.GraphicalItems():
        if g.GetLayer() != pcbnew.F_Fab or g.GetClass() not in ("FP_SHAPE", "MGRAPHIC", "PCB_SHAPE"):
            continue
        bb = g.GetBoundingBox(); w = pcbnew.ToMM(g.GetWidth()) / 2
        if g.GetShape() == pcbnew.SHAPE_T_CIRCLE:
            w = w  # circle bbox includes stroke too
        xs += [mm(bb.GetX()) + w, mm(bb.GetRight()) - w]; ys += [mm(bb.GetY()) + w, mm(bb.GetBottom()) - w]
    body = [min(xs), min(ys), max(xs), max(ys)] if xs else None
    pads = []
    for p in fp.Pads():
        b = p.GetBoundingBox()
        pads.append([p.GetNumber(), p.GetNetname(), [mm(b.GetX()), mm(b.GetY()), mm(b.GetRight()), mm(b.GetBottom())],
                     p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH, p.IsOnLayer(pcbnew.F_Cu), p.IsOnLayer(pcbnew.F_Paste)])
    out[fp.GetReference()] = dict(value=fp.GetValue(), fpid=fp.GetFPIDAsString(), body=body, pads=pads,
                                  x=mm(fp.GetPosition().x), y=mm(fp.GetPosition().y), rot=fp.GetOrientationDegrees(),
                                  back=fp.GetLayer() == pcbnew.B_Cu)
json.dump(out, open(sys.argv[2], "w"), indent=0)
