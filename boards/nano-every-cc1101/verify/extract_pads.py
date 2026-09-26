# KiCad side for gerber_nets.py: every pad and via with its net, position and drill.
import pcbnew, json, sys
B = pcbnew.LoadBoard(sys.argv[1]); mm = lambda v: pcbnew.ToMM(v) - 100
pads, vias = [], []
for fp in B.GetFootprints():
    for p in fp.Pads():
        pads.append(dict(ref=fp.GetReference(), num=p.GetNumber(), net=p.GetNetname(), x=mm(p.GetPosition().x), y=mm(p.GetPosition().y),
                         top=p.IsOnLayer(pcbnew.F_Cu), bot=p.IsOnLayer(pcbnew.B_Cu), drill=pcbnew.ToMM(p.GetDrillSize().x) if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 0,
                         npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH, sx=pcbnew.ToMM(p.GetSize().x), sy=pcbnew.ToMM(p.GetSize().y), smd=p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD, fmask=p.IsOnLayer(pcbnew.F_Mask), bmask=p.IsOnLayer(pcbnew.B_Mask)))
for t in B.GetTracks():
    if t.GetClass() == "PCB_VIA":
        vias.append(dict(net=t.GetNetname(), x=mm(t.GetPosition().x), y=mm(t.GetPosition().y), d=pcbnew.ToMM(t.GetWidth()), drill=pcbnew.ToMM(t.GetDrillValue())))
json.dump(dict(pads=pads, vias=vias), open(sys.argv[2], "w"))
print(len(pads), "pads", len(vias), "vias")
