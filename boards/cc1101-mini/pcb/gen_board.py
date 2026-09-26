#!/usr/bin/env python3
"""Generate the placed-and-routed CC1101 mini board (cc1101_mini.kicad_pcb).

Run with the Python that ships KiCad 7's `pcbnew` module (on Debian/Ubuntu:
`/usr/bin/python3 gen_board.py` after `apt install kicad kicad-footprints`).
Everything is described below in board coordinates (mm, origin = top-left
board corner, +y down) so the layout can be reviewed and tweaked as code,
then re-opened and hand-edited in KiCad.

Circuit: TI CC1101 with the datasheet's 315/433 MHz application circuit
(SWRS061I Figure 10 / Table 21, 433 MHz column), a 26 MHz crystal, a U.FL
antenna connector and a 1x8 1.27 mm header carrying SPI + GDO0/GDO2 + power.
4-layer stackup: F.Cu signals, In1.Cu solid GND, In2.Cu VCC plane, B.Cu
digital escape routes + GND pour.
"""

from __future__ import annotations

import math
import os
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "cc1101_mini.kicad_pcb")
FP_ROOT = os.environ.get("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")

# Board outline and origin offset (KiCad sheet coordinates).
BOARD_W, BOARD_H = 18.5, 12.6
OX, OY = 100.0, 100.0

TRACK = 0.15      # default signal track
PWR = 0.25        # short power stubs
RF_BAL = 0.25     # balun / pin-escape section (sub-mm, not length-critical)
RF_50 = 0.40      # ~49 ohm CPWG (0.25 mm gap) on JLC04161H-7628, L1->L2 0.21 mm
VIA_D, VIA_DRILL = 0.45, 0.2

# ---------------------------------------------------------------------------
# Parts: ref -> (library, footprint, x, y, rotation, value, {pad: net})
# Rotation 90 puts pad 1 of a 2-pin chip at the *bottom* (+y).
# ---------------------------------------------------------------------------
QFN = ("Package_DFN_QFN", "Texas_RGP0020H_VQFN-20-1EP_4x4mm_P0.5mm_EP2.4x2.4mm")
C0402 = ("Capacitor_SMD", "C_0402_1005Metric")
L0402 = ("Inductor_SMD", "L_0402_1005Metric")
R0402 = ("Resistor_SMD", "R_0402_1005Metric")

PARTS = {
    "U1": (*QFN, 6.5, 6.0, 0, "CC1101RGPR", {
        "1": "SCLK", "2": "SO", "3": "GDO2", "4": "VCC", "5": "DCOUPL",
        "6": "GDO0", "7": "CSN", "8": "XOSC_Q1", "9": "VCC", "10": "XOSC_Q2",
        "11": "VCC", "12": "RF_P", "13": "RF_N", "14": "VCC", "15": "VCC",
        "16": "GND", "17": "RBIAS", "18": "VCC", "19": "GND", "20": "SI",
        "21": "GND"}),
    "Y1": ("Crystal", "Crystal_SMD_3225-4Pin_3.2x2.5mm", 6.6, 10.6, 0, "26MHz",
           {"1": "XOSC_Q1", "2": "GND", "3": "XOSC_Q2", "4": "GND"}),
    "C81": (*C0402, 3.9, 11.2, 90, "27pF", {"1": "GND", "2": "XOSC_Q1"}),
    "C101": (*C0402, 9.35, 11.2, 90, "27pF", {"1": "GND", "2": "XOSC_Q2"}),
    "C41": (*C0402, 3.35, 7.8, 90, "100nF", {"1": "GND", "2": "VCC"}),
    "C51": (*C0402, 4.3, 7.95, 90, "100nF", {"1": "GND", "2": "DCOUPL"}),
    "R171": (*R0402, 7.6, 2.3, 90, "56k 1%", {"1": "RBIAS", "2": "GND"}),
    "C181": (*C0402, 5.75, 1.3, 0, "100nF", {"1": "GND", "2": "VCC"}),
    "C151": (*C0402, 8.85, 2.3, 90, "100nF", {"1": "VCC", "2": "GND"}),
    "C111": (*C0402, 9.2, 8.95, 90, "100nF", {"1": "GND", "2": "VCC"}),
    "C1": (*C0402, 3.85, 1.3, 0, "1uF", {"1": "VCC", "2": "GND"}),
    # 433 MHz balun (datasheet Figure 10)
    "C131": (*C0402, 9.85, 3.85, 90, "3.9pF", {"1": "RF_N", "2": "GND"}),
    "L131": (*L0402, 10.35, 5.55, 0, "27nH", {"1": "RF_N", "2": "RF_J"}),
    "C121": (*C0402, 10.35, 6.95, 0, "3.9pF", {"1": "RF_P", "2": "RF_J"}),
    "L121": (*L0402, 10.35, 8.45, 90, "27nH", {"1": "RF_L121", "2": "RF_P"}),
    "C124": (*C0402, 10.35, 10.6, 90, "220pF", {"1": "GND", "2": "RF_L121"}),
    # LC low-pass filter + DC block to antenna
    "L122": (*L0402, 12.25, 6.25, 0, "22nH", {"1": "RF_J", "2": "RF_F1"}),
    "C122": (*C0402, 12.75, 7.95, 90, "8.2pF", {"1": "GND", "2": "RF_F1"}),
    "L123": (*L0402, 14.15, 6.25, 0, "27nH", {"1": "RF_F1", "2": "RF_F2"}),
    "C123": (*C0402, 14.65, 7.95, 90, "5.6pF", {"1": "GND", "2": "RF_F2"}),
    "C125": (*C0402, 16.0, 5.45, 90, "220pF", {"1": "RF_F2", "2": "ANT"}),
    "J1": ("Connector_Coaxial", "U.FL_Hirose_U.FL-R-SMT-1_Vertical", 16.0, 2.45, 90,
           "U.FL", {"1": "ANT", "2": "GND"}),
    "J2": ("Connector_PinHeader_1.27mm", "PinHeader_1x08_P1.27mm_Vertical", 1.3, 1.8, 0,
           "1x08 1.27mm", {"1": "VCC", "2": "GND", "3": "SI", "4": "SCLK", "5": "SO",
                           "6": "GDO2", "7": "GDO0", "8": "CSN"}),
}

HEADER_LABELS = ["3V3", "GND", "MOSI", "SCK", "MISO", "GDO2", "GDO0", "CSn"]


def main() -> int:
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FromMM(1.6))
    ds.m_TrackMinWidth = FromMM(0.127)
    ds.m_MinClearance = FromMM(0.127)
    ds.m_ViasMinSize = FromMM(0.45)
    ds.m_ViasMinAnnularWidth = FromMM(0.1)
    ds.m_MinThroughDrill = FromMM(0.2)
    ds.m_CopperEdgeClearance = FromMM(0.25)
    ds.m_HoleToHoleMin = FromMM(0.25)
    ds.m_HoleClearance = FromMM(0.2)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(FromMM(0.15))
    nc.SetTrackWidth(FromMM(TRACK))
    nc.SetViaDiameter(FromMM(VIA_D))
    nc.SetViaDrill(FromMM(VIA_DRILL))

    nets: dict[str, pcbnew.NETINFO_ITEM] = {}

    def net(name: str) -> pcbnew.NETINFO_ITEM:
        if name not in nets:
            n = pcbnew.NETINFO_ITEM(board, name)
            board.Add(n)
            nets[name] = n
        return nets[name]

    def pt(x: float, y: float) -> VECTOR2I:
        return VECTOR2I(FromMM(OX + x), FromMM(OY + y))

    fps: dict[str, pcbnew.FOOTPRINT] = {}
    for ref, (lib, name, x, y, rot, value, padnets) in PARTS.items():
        fp = pcbnew.FootprintLoad(os.path.join(FP_ROOT, lib + ".pretty"), name)
        if fp is None:
            print(f"error: footprint {lib}:{name} not found under {FP_ROOT}", file=sys.stderr)
            return 1
        fp.SetFPIDAsString(f"{lib}:{name}")
        fp.SetReference(ref)
        fp.SetValue(value)
        board.Add(fp)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            if pad.GetNumber() in padnets:
                pad.SetNet(net(padnets[pad.GetNumber()]))
        # Tiny board: reference designators live in the assembly drawing
        # (F.Fab), not on the silkscreen, which has no room for them.
        fp.Reference().SetLayer(pcbnew.F_Fab)
        fp.Reference().SetTextSize(VECTOR2I(FromMM(0.4), FromMM(0.4)))
        fp.Reference().SetTextThickness(FromMM(0.06))
        fp.Reference().SetPosition(fp.GetPosition())
        fp.Value().SetVisible(False)
        fps[ref] = fp

    def P(ref: str, num: str) -> tuple[float, float]:
        for pad in fps[ref].Pads():
            if pad.GetNumber() == num:
                pos = pad.GetPosition()
                return (round(pcbnew.ToMM(pos.x) - OX, 4), round(pcbnew.ToMM(pos.y) - OY, 4))
        raise KeyError(f"{ref}.{num}")

    def track(netname: str, pts, width=TRACK, layer=pcbnew.F_Cu):
        pts = [P(*p) if isinstance(p[0], str) else p for p in pts]
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pt(*a))
            t.SetEnd(pt(*b))
            t.SetWidth(FromMM(width))
            t.SetLayer(layer)
            t.SetNet(net(netname))
            board.Add(t)

    def via(netname: str, x: float, y: float):
        v = pcbnew.PCB_VIA(board)
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetPosition(pt(x, y))
        v.SetWidth(FromMM(VIA_D))
        v.SetDrill(FromMM(VIA_DRILL))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(net(netname))
        board.Add(v)

    B = pcbnew.B_Cu

    # ---------------- digital interface: pad -> via -> B.Cu -> header -----
    track("SI", [("U1", "20"), (5.5, 3.3), (5.0, 2.8)])
    via("SI", 5.0, 2.8)
    track("SI", [(5.0, 2.8), (3.46, 4.34), ("J2", "3")], layer=B)

    track("SCLK", [("U1", "1"), (3.7, 5.0)])
    via("SCLK", 3.7, 5.0)
    track("SCLK", [(3.7, 5.0), (2.2, 5.0), (1.59, 5.61), ("J2", "4")], layer=B)

    track("SO", [("U1", "2"), (3.1, 5.5)])
    via("SO", 3.1, 5.5)
    track("SO", [(3.1, 5.5), (1.72, 6.88), ("J2", "5")], layer=B)

    track("GDO2", [("U1", "3"), (3.7, 6.0)])
    via("GDO2", 3.7, 6.0)
    track("GDO2", [(3.7, 6.0), (3.7, 6.9), (2.45, 8.15), ("J2", "6")], layer=B)

    track("GDO0", [("U1", "6"), (5.5, 8.4), (5.3, 8.65)])
    via("GDO0", 5.3, 8.65)
    track("GDO0", [(5.3, 8.65), (4.3, 9.65), (1.9, 9.65), ("J2", "7")], layer=B)

    track("CSN", [("U1", "7"), (6.0, 8.75)])
    via("CSN", 6.0, 8.75)
    track("CSN", [(6.0, 8.75), (4.06, 10.69), ("J2", "8")], layer=B)

    # ---------------- power ------------------------------------------------
    # Header pin 1 is through-hole, so it lands on the In2.Cu VCC plane too.
    track("VCC", [("J2", "1"), ("C1", "1")], width=PWR)
    # DVDD (pin 4): pad -> via -> C41
    track("VCC", [("U1", "4"), (3.35, 6.5), ("C41", "2")], width=PWR)
    via("VCC", 3.2, 6.5)
    # DCOUPL (pin 5) -> C51 (1.8 V core regulator output, NOT tied to VCC)
    track("DCOUPL", [("U1", "5"), (4.3, 7.0), ("C51", "2")], width=PWR)
    # DGUARD (pin 18) -> via -> C181
    track("VCC", [("U1", "18"), (6.5, 3.25), (6.4, 2.95)], width=PWR)
    via("VCC", 6.4, 2.95)
    track("VCC", [(6.4, 2.95), (6.4, 1.3), ("C181", "2")], width=PWR)
    # AVDD 14/15 -> via -> C151
    track("VCC", [("U1", "15"), (8.7, 5.0), (8.7, 5.5), ("U1", "14")], width=PWR)
    track("VCC", [(8.7, 5.0), (8.85, 4.75), (8.85, 4.1)], width=PWR)
    via("VCC", 8.85, 4.1)
    track("VCC", [(8.85, 4.1), ("C151", "1")], width=PWR)
    # AVDD 11 -> via -> C111
    track("VCC", [("U1", "11"), (9.0, 7.0), (9.2, 7.35)], width=PWR)
    via("VCC", 9.2, 7.35)
    track("VCC", [(9.2, 7.35), ("C111", "2")], width=PWR)
    # AVDD 9 -> via (sits between the two crystal nets)
    track("VCC", [("U1", "9"), (7.0, 8.75)], width=PWR)
    via("VCC", 7.0, 8.75)

    # RBIAS
    track("RBIAS", [("U1", "17"), (7.0, 3.35), ("R171", "1")])

    # Ground pins 16/19 straight into the exposed pad
    track("GND", [("U1", "19"), (6.0, 5.0)], width=PWR)
    track("GND", [("U1", "16"), (7.5, 5.0)], width=PWR)

    # ---------------- crystal ---------------------------------------------
    track("XOSC_Q1", [("U1", "8"), (6.5, 11.45), ("Y1", "1")])
    track("XOSC_Q1", [("Y1", "1"), (4.5, 10.72), ("C81", "2")])
    track("XOSC_Q2", [("U1", "10"), (7.5, 9.2), ("Y1", "3")])
    track("XOSC_Q2", [("Y1", "3"), (8.25, 10.2), (9.35, 10.2), ("C101", "2")])

    # ---------------- RF: balun + filter -----------------------------------
    track("RF_N", [("U1", "13"), (9.25, 6.0), (9.7, 5.55), ("L131", "1")], width=RF_BAL)
    track("RF_N", [("C131", "1"), ("L131", "1")], width=RF_BAL)
    track("RF_P", [("U1", "12"), (9.25, 6.5), (9.7, 6.95), ("C121", "1")], width=RF_BAL)
    track("RF_P", [("C121", "1"), ("L121", "2")], width=RF_BAL)
    track("RF_L121", [("L121", "1"), ("C124", "2")], width=RF_BAL)
    track("RF_J", [("L131", "2"), (11.3, 5.55), (11.3, 6.95), ("C121", "2")], width=RF_BAL)
    track("RF_J", [(11.3, 6.25), ("L122", "1")], width=RF_50)
    track("RF_F1", [("L122", "2"), ("L123", "1")], width=RF_50)
    track("RF_F1", [("C122", "2"), (12.75, 6.25)], width=RF_50)
    track("RF_F2", [("L123", "2"), (16.0, 6.25), ("C125", "1")], width=RF_50)
    track("RF_F2", [("C123", "2"), (14.65, 6.25)], width=RF_50)
    track("ANT", [("C125", "2"), ("J1", "1")], width=RF_50)

    # ---------------- ground vias -----------------------------------------
    # 5 tented vias in the CC1101 exposed pad (per SWRS061I section 7.8)
    for dx, dy in [(0, 0), (-0.65, -0.65), (0.65, -0.65), (-0.65, 0.65), (0.65, 0.65)]:
        via("GND", 6.5 + dx, 6.0 + dy)
    # one via right at each decoupling / shunt ground pad
    gnd_escape = {
        "C1": (4.8, 0.75), "C181": (4.8, 0.75), "R171": (7.6, 1.2), "C151": (8.85, 1.2),
        "C131": (9.85, 2.95), "C41": (3.35, 9.0), "C51": (3.35, 9.0),
        "C111": (9.75, 9.6), "C124": (10.35, 11.9), "C122": (12.75, 8.95),
        "C123": (14.65, 8.95), "C101": (8.75, 12.0), "C81": (3.1, 11.68),
    }
    placed_gnd = set()
    for ref, (x, y) in gnd_escape.items():
        pad = "2" if PARTS[ref][6].get("2") == "GND" else "1"
        track("GND", [(ref, pad), (x, y)], width=PWR)
        if (x, y) not in placed_gnd:
            via("GND", x, y)
            placed_gnd.add((x, y))
    # Y1 pad 2 is boxed in by the XOSC_Q1 track; tie it to C101's ground via.
    track("GND", [("Y1", "2"), (8.75, 12.0)], width=PWR)

    # ---------------- outline ---------------------------------------------
    edge = pcbnew.PCB_SHAPE(board)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(pt(0, 0))
    edge.SetEnd(pt(BOARD_W, BOARD_H))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(FromMM(0.1))
    board.Add(edge)
    # Fab outputs (drill, placement) are referenced to the lower-left corner.
    ds.SetAuxOrigin(pt(0, BOARD_H))
    ds.SetGridOrigin(pt(0, BOARD_H))

    # ---------------- zones -------------------------------------------------
    def zone(netname: str, layer: int, clearance: float, priority: int = 0):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(net(netname))
        z.SetLocalClearance(FromMM(clearance))
        z.SetMinThickness(FromMM(0.2))
        z.SetThermalReliefGap(FromMM(0.2))
        z.SetThermalReliefSpokeWidth(FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(priority)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]:
            ol.Append(FromMM(OX + x), FromMM(OY + y))
        board.Add(z)
        return z

    zone("GND", pcbnew.F_Cu, 0.25)
    zone("GND", pcbnew.In1_Cu, 0.2)
    zone("VCC", pcbnew.In2_Cu, 0.2)
    zone("GND", pcbnew.B_Cu, 0.2)

    # ---------------- ground stitching -------------------------------------
    stitch_ground(board, net("GND"), pt, via)

    # ---------------- silkscreen -------------------------------------------
    def text(s, x, y, layer, size=0.6, mirror=False, just=pcbnew.GR_TEXT_H_ALIGN_CENTER):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(pt(x, y))
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(size * 0.15))
        t.SetMirrored(mirror)
        t.SetHorizJustify(just)
        board.Add(t)

    # Header pin-1 marks on both sides, and a pin legend in the empty
    # lower-right area of the bottom (the header sits too close to the
    # escape vias to label each pin in place).
    x1, y1 = P("J2", "1")
    text("1", x1 + 1.1, y1, pcbnew.B_SilkS, size=0.8, mirror=True)
    text("CC1101 433M v1", 12.9, 7.2, pcbnew.B_SilkS, size=0.8, mirror=True)
    for i, label in enumerate(HEADER_LABELS):
        col, row = divmod(i, 4)
        text(f"{i + 1} {label}", 15.6 - col * 5.4, 8.4 + row * 1.05, pcbnew.B_SilkS,
             size=0.8, mirror=True)
    text("ANT", 12.6, 2.45, pcbnew.F_SilkS, size=0.8)

    # Zone filling needs a board that went through KiCad's loader (it
    # segfaults on a purely in-memory BOARD), so save, reload, fill, save.
    pcbnew.SaveBoard(OUT, board)
    board = pcbnew.LoadBoard(OUT)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(OUT, board)
    print(f"wrote {OUT}")
    return 0


def stitch_ground(board, gnd, pt, via, pitch=1.3, clearance=0.2):
    """Drop GND vias on a grid wherever they clear every other-net copper
    object on any layer (vias are through-hole) and stay off the board edge
    and out from under parts."""
    r = VIA_D / 2

    def mm(v):
        return pcbnew.ToMM(v)

    obstacles = []  # (kind, geometry, net)
    for fp in board.GetFootprints():
        bb = fp.GetBoundingBox(False, False)
        obstacles.append(("keepout", (mm(bb.GetX()) - OX, mm(bb.GetY()) - OY,
                                      mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY), None))
        for pad in fp.Pads():
            b = pad.GetBoundingBox()
            obstacles.append(("rect", (mm(b.GetX()) - OX, mm(b.GetY()) - OY,
                                       mm(b.GetRight()) - OX, mm(b.GetBottom()) - OY),
                              pad.GetNetname()))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            p = t.GetPosition()
            obstacles.append(("circle", (mm(p.x) - OX, mm(p.y) - OY, mm(t.GetWidth()) / 2),
                              t.GetNetname()))
        else:
            s, e = t.GetStart(), t.GetEnd()
            obstacles.append(("seg", (mm(s.x) - OX, mm(s.y) - OY, mm(e.x) - OX, mm(e.y) - OY,
                                      mm(t.GetWidth()) / 2), t.GetNetname()))

    def dist_rect(x, y, x0, y0, x1, y1):
        dx = max(x0 - x, 0, x - x1)
        dy = max(y0 - y, 0, y - y1)
        return math.hypot(dx, dy)

    def dist_seg(x, y, ax, ay, bx, by):
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * vx + (y - ay) * vy) / L2))
        return math.hypot(x - (ax + u * vx), y - (ay + u * vy))

    placed = []
    edge_margin = 0.45
    ny = int(BOARD_H / pitch) + 1
    nx = int(BOARD_W / pitch) + 1
    for iy in range(ny):
        for ix in range(nx):
            x = 0.55 + ix * pitch
            y = 0.55 + iy * pitch
            if not (edge_margin <= x <= BOARD_W - edge_margin and
                    edge_margin <= y <= BOARD_H - edge_margin):
                continue
            ok = True
            for kind, g, n in obstacles:
                if kind == "keepout":
                    if g[0] < x < g[2] and g[1] < y < g[3]:
                        ok = False
                elif kind == "circle" and n == "GND":
                    ok = math.hypot(x - g[0], y - g[1]) >= r + g[2] + 0.15
                elif n == "GND":
                    continue
                elif kind == "rect":
                    ok = dist_rect(x, y, *g) >= r + clearance
                elif kind == "circle":
                    ok = math.hypot(x - g[0], y - g[1]) >= r + g[2] + clearance
                elif kind == "seg":
                    ok = dist_seg(x, y, *g[:4]) >= r + g[4] + clearance
                if not ok:
                    break
            if ok and all(math.hypot(x - px, y - py) >= VIA_D + 0.3 for px, py in placed):
                via("GND", x, y)
                placed.append((x, y))
    # GND vias also must not crowd each other/existing GND vias: handled by
    # grid pitch; existing GND vias are allowed to be close (same net).
    return placed


if __name__ == "__main__":
    raise SystemExit(main())
