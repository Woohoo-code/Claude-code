import pcbnew, json, sys
B = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
out = {}
for fp in B.GetFootprints():
    pads = []
    for p in fp.Pads():
        pads.append([p.GetNumber(), mm(p.GetPosition().x) - 100, mm(p.GetPosition().y) - 100,
                     p.IsOnLayer(pcbnew.F_Cu), p.IsOnLayer(pcbnew.B_Cu), p.GetNetname()])
    out[fp.GetReference()] = dict(fpid=fp.GetFPIDAsString(), value=fp.GetValue(),
        x=mm(fp.GetPosition().x) - 100, y=mm(fp.GetPosition().y) - 100,
        rot=fp.GetOrientationDegrees(), pads=pads)
json.dump(out, open(sys.argv[2], "w"))
print(len(out), "footprints")
