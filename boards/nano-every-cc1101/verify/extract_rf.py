import pcbnew, json, sys
B = pcbnew.LoadBoard(sys.argv[1]); mm = lambda v: pcbnew.ToMM(v) - 100.0
nets = ["ANT_A", "M_433", "FEED_433", "M_315", "FEED_315", "SMA_A",
        "ANT_B", "M_868", "FEED_868", "M_915", "FEED_915", "SMA_B"]
out = {"segs": [], "pads": []}
for t in B.GetTracks():
    if t.GetClass() == "PCB_TRACK" and t.GetNetname() in nets:
        a, b = t.GetStart(), t.GetEnd()
        out["segs"].append([t.GetNetname(), [mm(a.x), mm(a.y)], [mm(b.x), mm(b.y)], pcbnew.ToMM(t.GetWidth())])
for fp in B.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() in nets:
            bb = p.GetBoundingBox()
            out["pads"].append([fp.GetReference(), p.GetNumber(), p.GetNetname(),
                                [mm(p.GetPosition().x), mm(p.GetPosition().y)],
                                [mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom())], fp.GetValue()])
json.dump(out, open(sys.argv[2], "w"))
print(len(out["segs"]), "segments,", len(out["pads"]), "pads")
