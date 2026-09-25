#!/usr/bin/env python3
"""Generate nano_every_cc1101.kicad_pcb: a 100 x 100 mm, 2-layer carrier for
an Arduino Nano Every with two TI CC1101 radios covering every CC1101 band:

  radio A (U1)   : 315 / 433 MHz front end (433 MHz BOM fitted)
                   -> printed IFA 433 (top edge), printed IFA 315 (left edge),
                      SMA J1 / wire H1
  radio B (U501) : 868 / 915 MHz front end
                   -> printed IFA 868 and IFA 915 (right edge), SMA J2 / wire H2

Every antenna branch starts with a series selector part (fit it to use that
antenna, leave it off otherwise), then a shunt part and a second series
part: a T-match right at the antenna feed, valued from the openEMS model
(antenna/match.py).

Run with KiCad 7's Python (`/usr/bin/python3 gen_board.py`). Steps:
  1. place parts; hand-route both CC1101 clusters (radio A = the
     boards/cc1101-mini layout rotated 90 deg; radio B = the same core with
     TI's 868/915 MHz balun), every RF line, match network and antenna, the
     LDO/level-shifter power stubs and the Nano breakout links
  2. autoroute the remaining digital/power nets with Freerouting (GND is
     excluded: it lands on the pours through its own vias)
  3. stitch and pour ground on both layers, save

Coordinates: board mm, origin top-left, +y down.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys

import pcbnew
from pcbnew import FromMM, VECTOR2I

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "antenna"))
import antenna_geometry as ag  # noqa: E402
from antenna_geometry import BOARD, GND_X0, GND_X1, GND_Y0, TRACE_W as ANT_W  # noqa: E402
from match import MATCH  # noqa: E402

OUT = os.path.join(HERE, "nano_every_cc1101.kicad_pcb")
FP_ROOT = os.environ.get("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
LOCAL_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
FREEROUTING = os.environ.get("FREEROUTING_JAR", "/tmp/claude-0/freerouting.jar")
OX, OY = 100.0, 100.0

TRACK = 0.25
PWR = 0.5
CL_TRACK, CL_PWR = 0.15, 0.25
RF_BAL, RF_IN, RF_SEL = 0.25, 0.4, 0.6
RF_50 = 1.2          # ~51 ohm CPWG, 0.2 mm gap, 1.6 mm FR4
VIA_D, VIA_DRILL = 0.6, 0.3
CL_VIA_D, CL_VIA_DRILL = 0.5, 0.25

C0402 = ("Capacitor_SMD", "C_0402_1005Metric")
L0402 = ("Inductor_SMD", "L_0402_1005Metric")
R0402 = ("Resistor_SMD", "R_0402_1005Metric")
C0603 = ("Capacitor_SMD", "C_0603_1608Metric")
R0603 = ("Resistor_SMD", "R_0603_1608Metric")
L0603 = ("Inductor_SMD", "L_0603_1608Metric")
QFN = ("Package_DFN_QFN", "Texas_RGP0020H_VQFN-20-1EP_4x4mm_P0.5mm_EP2.4x2.4mm")

# ---------------------------------------------------------------------------
# CC1101 core in boards/cc1101-mini coordinates (U centre = (6.5, 6.0)).
# Refdes are TI's (U1, C121, ...); radio B adds 500 (U501, C621, ...).
# Net names ending in "*" get the radio suffix (_A / _B); others are shared.
# ---------------------------------------------------------------------------
CORE = {
    "U1": (*QFN, 6.5, 6.0, 0, "CC1101RGPR", {
        "1": "SCLK", "2": "SO", "3": "GDO2*", "4": "3V3", "5": "DCOUPL*",
        "6": "GDO0*", "7": "CSN*", "8": "XOSC_Q1*", "9": "3V3", "10": "XOSC_Q2*",
        "11": "3V3", "12": "RF_P*", "13": "RF_N*", "14": "3V3", "15": "3V3",
        "16": "GND", "17": "RBIAS*", "18": "3V3", "19": "GND", "20": "SI", "21": "GND"}),
    "Y1": ("Crystal", "Crystal_SMD_3225-4Pin_3.2x2.5mm", 6.6, 10.6, 0, "26MHz",
           {"1": "XOSC_Q1*", "2": "GND", "3": "XOSC_Q2*", "4": "GND"}),
    "C81": (*C0402, 3.9, 11.2, 90, "27pF", {"1": "GND", "2": "XOSC_Q1*"}),
    "C101": (*C0402, 9.35, 11.2, 90, "27pF", {"1": "GND", "2": "XOSC_Q2*"}),
    "C41": (*C0402, 3.35, 7.8, 90, "100nF", {"1": "GND", "2": "3V3"}),
    "C51": (*C0402, 4.3, 7.95, 90, "100nF", {"1": "GND", "2": "DCOUPL*"}),
    "R171": (*R0402, 7.6, 2.3, 90, "56k 1%", {"1": "RBIAS*", "2": "GND"}),
    "C181": (*C0402, 5.75, 1.3, 0, "100nF", {"1": "GND", "2": "3V3"}),
    "C151": (*C0402, 8.85, 2.3, 90, "100nF", {"1": "3V3", "2": "GND"}),
    "C111": (*C0402, 9.2, 8.95, 90, "100nF", {"1": "GND", "2": "3V3"}),
}
CORE_GND_ESCAPE = {
    "C181": (4.8, 0.75), "R171": (7.6, 1.2), "C151": (8.85, 1.2),
    "C41": (3.35, 9.0), "C51": (3.35, 9.0), "C111": (9.75, 9.6),
    "C101": (8.75, 12.0), "C81": (3.1, 11.68),
}

# 315/433 MHz balun + LC filter (SWRS061I Fig. 10, 433 MHz values)
RF_433 = {
    "C131": (*C0402, 9.85, 3.85, 90, "3.9pF", {"1": "RF_N*", "2": "GND"}),
    "L131": (*L0402, 10.35, 5.55, 0, "27nH", {"1": "RF_N*", "2": "RF_J*"}),
    "C121": (*C0402, 10.35, 6.95, 0, "3.9pF", {"1": "RF_P*", "2": "RF_J*"}),
    "L121": (*L0402, 10.35, 8.45, 90, "27nH", {"1": "RF_L121*", "2": "RF_P*"}),
    "C124": (*C0402, 10.35, 10.6, 90, "220pF", {"1": "GND", "2": "RF_L121*"}),
    "L122": (*L0402, 12.25, 6.25, 0, "22nH", {"1": "RF_J*", "2": "RF_F1*"}),
    "C122": (*C0402, 12.75, 7.95, 90, "8.2pF", {"1": "GND", "2": "RF_F1*"}),
    "L123": (*L0402, 14.15, 6.25, 0, "27nH", {"1": "RF_F1*", "2": "RF_F2*"}),
    "C123": (*C0402, 14.65, 7.95, 90, "5.6pF", {"1": "GND", "2": "RF_F2*"}),
    "C125": (*C0402, 16.0, 5.45, 90, "220pF", {"1": "RF_F2*", "2": "ANT*"}),
}
RF_433_GND = {"C131": (9.85, 2.95), "C124": (10.35, 11.9), "C122": (12.75, 8.95),
              "C123": (14.65, 8.95)}

# 868/915 MHz balun + filter (SWRS061I Fig. 11): L121/L131 in series with
# the pins, C121 across them, C131 shunt + L132 series on the N side,
# L122+C124 shunt + C122 series on the P side, joined at J, then
# L123 - C123 - L124 - C125.
RF_868 = {
    "L131": (*L0402, 10.35, 5.55, 0, "12nH", {"1": "RF_N*", "2": "RF_N1*"}),
    "L121": (*L0402, 10.35, 6.95, 0, "12nH", {"1": "RF_P*", "2": "RF_P1*"}),
    "C121": (*C0402, 11.75, 6.25, 90, "1.0pF", {"2": "RF_N1*", "1": "RF_P1*"}),
    "C131": (*C0402, 11.75, 3.9, 90, "1.5pF", {"1": "RF_N1*", "2": "GND"}),
    "L132": (*L0402, 13.4, 4.6, 0, "18nH", {"1": "RF_N1*", "2": "RF_J*"}),
    "L122": (*L0402, 11.75, 8.6, 90, "18nH", {"2": "RF_P1*", "1": "RF_L122*"}),
    "C124": (*C0402, 11.75, 10.6, 90, "100pF", {"2": "RF_L122*", "1": "GND"}),
    "C122": (*C0402, 13.4, 7.2, 0, "1.5pF", {"1": "RF_P1*", "2": "RF_J*"}),
    "L123": (*L0402, 15.9, 5.9, 0, "12nH", {"1": "RF_J*", "2": "RF_F1*"}),
    "C123": (*C0402, 16.4, 7.6, 90, "3.3pF", {"2": "RF_F1*", "1": "GND"}),
    "L124": (*L0402, 17.9, 5.9, 0, "12nH", {"1": "RF_F1*", "2": "RF_F2*"}),
    "C125": (*C0402, 19.85, 5.9, 0, "12pF", {"1": "RF_F2*", "2": "ANT*"}),
}
RF_868_GND = {"C131": (11.75, 2.55), "C124": (11.75, 11.95), "C123": (16.4, 9.0)}

RADIO_A_AT, RADIO_B_AT = (34.0, 42.0), (64.5, 45.0)

NANO_X0, NANO_Y0 = 42.4, 57.0         # Nano pad 1 (rotation 0: USB at the bottom)
NANO_PINS = {
    1: ("D1_TX", "TX"), 2: ("D0_RX", "RX"), 3: ("RST", "RST"), 4: ("GND", "GND"),
    5: ("D2", "D2"), 6: ("D3", "D3"), 7: ("D4", "D4"), 8: ("D5", "D5"),
    9: ("D6", "D6"), 10: ("D7", "D7"), 11: ("D8", "D8"), 12: ("D9", "D9"),
    13: ("D10", "D10"), 14: ("D11_MOSI", "D11"), 15: ("D12_MISO", "D12"),
    16: ("D13_SCK", "D13"), 17: ("3V3_NANO", "3V3"), 18: ("AREF", "REF"),
    19: ("A0", "A0"), 20: ("A1", "A1"), 21: ("A2", "A2"), 22: ("A3", "A3"),
    23: ("A4_SDA", "A4"), 24: ("A5_SCL", "A5"), 25: ("A6", "A6"), 26: ("A7", "A7"),
    27: ("+5V", "5V"), 28: ("RST", "RST"), 29: ("GND", "GND"), 30: ("VIN", "VIN"),
}
# TXS0108E: channel -> (A side @3.3 V, B side @5 V)
TXS = {1: ("SCLK", "D13_SCK"), 2: ("SI", "D11_MOSI"), 3: ("SO", "D12_MISO"),
       4: ("CSN_A", "D10"), 5: ("GDO0_A", "D2"), 6: ("GDO2_A", "D3"),
       7: ("CSN_B", "D9"), 8: ("GDO0_B", "D4")}
TXS_A_PIN = {1: "1", 2: "3", 3: "4", 4: "5", 5: "6", 6: "7", 7: "8", 8: "9"}
TXS_B_PIN = {1: "20", 2: "18", 3: "17", 4: "16", 5: "15", 6: "14", 7: "13", 8: "12"}


class Builder:
    def __init__(self):
        self.board = pcbnew.BOARD()
        self.board.SetCopperLayerCount(2)
        ds = self.ds = self.board.GetDesignSettings()
        ds.SetBoardThickness(FromMM(1.6))
        ds.m_TrackMinWidth = FromMM(0.15)
        ds.m_MinClearance = FromMM(0.15)
        ds.m_ViasMinSize = FromMM(0.5)
        ds.m_ViasMinAnnularWidth = FromMM(0.125)
        ds.m_MinThroughDrill = FromMM(0.25)
        ds.m_CopperEdgeClearance = FromMM(0.3)
        ds.m_HoleToHoleMin = FromMM(0.3)
        ds.m_HoleClearance = FromMM(0.2)
        nc = ds.m_NetSettings.m_DefaultNetClass
        nc.SetClearance(FromMM(0.15))
        nc.SetTrackWidth(FromMM(TRACK))
        nc.SetViaDiameter(FromMM(VIA_D))
        nc.SetViaDrill(FromMM(VIA_DRILL))
        self.nets = {}
        self.fps = {}
        self.created = []
        self.gnd_vias = []

    def pt(self, x, y):
        return VECTOR2I(FromMM(OX + x), FromMM(OY + y))

    def net(self, name):
        if name not in self.nets:
            n = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def fp(self, ref, lib, name, x, y, rot, value, padnets):
        root = LOCAL_LIB if lib == "nano_every_cc1101" else FP_ROOT
        fp = pcbnew.FootprintLoad(os.path.join(root, lib + ".pretty"), name)
        if fp is None:
            raise SystemExit(f"footprint {lib}:{name} not found under {FP_ROOT}")
        fp.SetFPIDAsString(f"{lib}:{name}")
        fp.SetReference(ref)
        fp.SetValue(value)
        self.board.Add(fp)
        fp.SetPosition(self.pt(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            if padnets.get(pad.GetNumber()):
                pad.SetNet(self.net(padnets[pad.GetNumber()]))
        r = fp.Reference()
        r.SetLayer(pcbnew.F_Fab)
        r.SetTextSize(VECTOR2I(FromMM(0.4), FromMM(0.4)))
        r.SetTextThickness(FromMM(0.06))
        r.SetPosition(fp.GetPosition())
        fp.Value().SetVisible(False)
        self.fps[ref] = fp
        self.created.append(fp)
        return fp

    def P(self, ref, num):
        for pad in self.fps[ref].Pads():
            if pad.GetNumber() == num:
                p = pad.GetPosition()
                return (round(pcbnew.ToMM(p.x) - OX, 4), round(pcbnew.ToMM(p.y) - OY, 4))
        raise KeyError(f"{ref}.{num}")

    def track(self, netname, pts, width=TRACK, layer=pcbnew.F_Cu):
        pts = [self.P(*p) if isinstance(p[0], str) else p for p in pts]
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            t = pcbnew.PCB_TRACK(self.board)
            t.SetStart(self.pt(*a))
            t.SetEnd(self.pt(*b))
            t.SetWidth(FromMM(width))
            t.SetLayer(layer)
            t.SetNet(self.net(netname))
            t.SetLocked(True)
            self.board.Add(t)
            self.created.append(t)

    def via(self, netname, x, y, d=VIA_D, drill=VIA_DRILL):
        v = pcbnew.PCB_VIA(self.board)
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetPosition(self.pt(x, y))
        v.SetWidth(FromMM(d))
        v.SetDrill(FromMM(drill))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(self.net(netname))
        v.SetLocked(True)
        self.board.Add(v)
        self.created.append(v)
        return v

    def gnd_stub(self, ref, pad, dx, dy, width=PWR):
        """Ground stub from a pad to a via (vias go in after routing)."""
        x, y = self.P(ref, pad)
        self.track("GND", [(ref, pad), (x + dx, y + dy)], width)
        self.gnd_vias.append((x + dx, y + dy, VIA_D, VIA_DRILL))

    def two_pin(self, ref, lib, name, x, y, rot, value, near, near_net, far_net):
        """2-pin part whose pad closest to point `near` gets `near_net`."""
        f = self.fp(ref, lib, name, x, y, rot, value, {})
        pads = sorted(f.Pads(), key=lambda p: math.dist(
            (pcbnew.ToMM(p.GetPosition().x) - OX, pcbnew.ToMM(p.GetPosition().y) - OY), near))
        pads[0].SetNet(self.net(near_net))
        pads[1].SetNet(self.net(far_net))
        return pads[0].GetNumber(), pads[1].GetNumber()


# ======================= CC1101 radios =====================================
def build_radio(b: Builder, suffix: str, offset: int, band: str, at, rot: int):
    """Build one CC1101 cluster in mini coordinates, then rotate by `rot`
    about U and move U to `at`."""
    b.created = []

    def R(ref):
        m = re.match(r"([A-Z]+)(\d+)$", ref)
        return f"{m.group(1)}{int(m.group(2)) + offset}"

    def N(name):
        return name[:-1] + "_" + suffix if name.endswith("*") else name

    parts = dict(CORE)
    parts.update(RF_433 if band == "433" else RF_868)
    for ref, (lib, name, x, y, r, value, padnets) in parts.items():
        b.fp(R(ref), lib, name, x, y, r, value, {k: N(v) for k, v in padnets.items()})

    def T(net, pts, w, layer=pcbnew.F_Cu):
        b.track(N(net), [(R(p[0]), p[1]) if isinstance(p[0], str) else p for p in pts],
                w, layer)

    def V(net, x, y):
        b.via(N(net), x, y, CL_VIA_D, CL_VIA_DRILL)

    ct, cp = CL_TRACK, CL_PWR
    T("SI", [("U1", "20"), (5.5, 3.3), (5.0, 2.8)], ct); V("SI", 5.0, 2.8)
    T("SCLK", [("U1", "1"), (3.7, 5.0)], ct); V("SCLK", 3.7, 5.0)
    T("SO", [("U1", "2"), (3.1, 5.5)], ct); V("SO", 3.1, 5.5)
    T("GDO2*", [("U1", "3"), (3.72, 5.985)], ct); V("GDO2*", 3.72, 5.985)
    T("GDO0*", [("U1", "6"), (5.5, 8.4), (5.3, 8.65)], ct); V("GDO0*", 5.3, 8.65)
    T("CSN*", [("U1", "7"), (6.0, 8.75)], ct); V("CSN*", 6.0, 8.75)
    T("3V3", [("U1", "4"), (3.35, 6.5), ("C41", "2")], 0.2); V("3V3", 3.2, 6.5)
    T("DCOUPL*", [("U1", "5"), (4.3, 7.0), ("C51", "2")], cp)
    T("3V3", [("U1", "18"), (6.5, 3.25), (6.4, 2.95)], cp); V("3V3", 6.4, 2.95)
    T("3V3", [(6.4, 2.95), (6.4, 1.3), ("C181", "2")], cp)
    T("3V3", [("U1", "15"), (8.7, 5.0), (8.7, 5.5), ("U1", "14")], cp)
    T("3V3", [(8.7, 5.0), (8.85, 4.75), (8.85, 4.1)], cp); V("3V3", 8.85, 4.1)
    T("3V3", [(8.85, 4.1), ("C151", "1")], cp)
    T("3V3", [("U1", "11"), (9.0, 7.0), (9.2, 7.35)], cp); V("3V3", 9.2, 7.35)
    T("3V3", [(9.2, 7.35), ("C111", "2")], cp)
    T("3V3", [("U1", "9"), (7.0, 8.75)], cp); V("3V3", 7.0, 8.75)
    # B.Cu ring tying the AVDD/DGUARD vias together around U
    T("3V3", [(6.4, 2.95), (8.85, 4.1), (9.2, 7.35), (7.0, 8.75)], cp, pcbnew.B_Cu)
    T("RBIAS*", [("U1", "17"), (7.0, 3.35), ("R171", "1")], ct)
    T("GND", [("U1", "19"), (6.0, 5.0)], cp)
    T("GND", [("U1", "16"), (7.5, 5.0)], cp)
    T("XOSC_Q1*", [("U1", "8"), (6.5, 11.45), ("Y1", "1")], ct)
    T("XOSC_Q1*", [("Y1", "1"), (4.5, 10.72), ("C81", "2")], ct)
    T("XOSC_Q2*", [("U1", "10"), (7.5, 9.2), ("Y1", "3")], ct)
    T("XOSC_Q2*", [("Y1", "3"), (8.25, 10.2), (9.35, 10.2), ("C101", "2")], ct)
    T("RF_N*", [("U1", "13"), (9.25, 6.0), (9.7, 5.55), ("L131", "1")], RF_BAL)
    T("RF_P*", [("U1", "12"), (9.25, 6.5), (9.7, 6.95),
                ("C121", "1") if band == "433" else ("L121", "1")], RF_BAL)
    if band == "433":
        T("RF_N*", [("C131", "1"), ("L131", "1")], RF_BAL)
        T("RF_P*", [("C121", "1"), ("L121", "2")], RF_BAL)
        T("RF_L121*", [("L121", "1"), ("C124", "2")], RF_BAL)
        T("RF_J*", [("L131", "2"), (11.3, 5.55), (11.3, 6.95), ("C121", "2")], RF_BAL)
        T("RF_J*", [(11.3, 6.25), ("L122", "1")], RF_IN)
        T("RF_F1*", [("L122", "2"), ("L123", "1")], RF_IN)
        T("RF_F1*", [("C122", "2"), (12.75, 6.25)], RF_IN)
        T("RF_F2*", [("L123", "2"), (16.0, 6.25), ("C125", "1")], RF_IN)
        T("RF_F2*", [("C123", "2"), (14.65, 6.25)], RF_IN)
        rf_gnd = RF_433_GND
    else:
        T("RF_N1*", [("L131", "2"), (11.75, 5.55), ("C121", "2")], RF_BAL)
        T("RF_N1*", [("C131", "1"), (11.75, 4.6), (11.75, 5.55)], RF_BAL)
        T("RF_N1*", [(11.75, 4.6), ("L132", "1")], RF_BAL)
        T("RF_P1*", [("L121", "2"), (11.75, 6.95), ("C121", "1")], RF_BAL)
        T("RF_P1*", [("L122", "2"), (11.75, 6.95)], RF_BAL)
        T("RF_P1*", [(11.75, 7.2), ("C122", "1")], RF_BAL)
        T("RF_L122*", [("L122", "1"), ("C124", "2")], RF_BAL)
        T("RF_J*", [("L132", "2"), (14.6, 4.6), (14.6, 7.2), ("C122", "2")], RF_BAL)
        T("RF_J*", [(14.6, 5.9), ("L123", "1")], RF_IN)
        T("RF_F1*", [("L123", "2"), ("L124", "1")], RF_IN)
        T("RF_F1*", [("C123", "2"), (16.4, 5.9)], RF_IN)
        T("RF_F2*", [("L124", "2"), ("C125", "1")], RF_IN)
        rf_gnd = RF_868_GND

    # ground vias (exposed pad + one per ground pad) as markers that rotate
    # with the cluster; the vias themselves go in after autorouting
    gpts = [(6.5 + dx, 6.0 + dy)
            for dx, dy in [(0, 0), (-0.65, -0.65), (0.65, -0.65), (-0.65, 0.65), (0.65, 0.65)]]
    for ref, (x, y) in list(CORE_GND_ESCAPE.items()) + list(rf_gnd.items()):
        pad = "2" if parts[ref][6].get("2") == "GND" else "1"
        T("GND", [(ref, pad), (x, y)], cp)
        if (x, y) not in gpts:
            gpts.append((x, y))
    T("GND", [("Y1", "2"), (8.75, 12.0)], cp)
    markers = []
    for x, y in gpts:
        m = pcbnew.PCB_SHAPE(b.board)
        m.SetShape(pcbnew.SHAPE_T_CIRCLE)
        m.SetCenter(b.pt(x, y))
        m.SetEnd(b.pt(x + 0.1, y))
        m.SetLayer(pcbnew.Dwgs_User)
        b.board.Add(m)
        b.created.append(m)
        markers.append(m)

    pivot = b.pt(6.5, 6.0)
    delta = b.pt(*at) - pivot
    for item in b.created:
        if rot:
            item.Rotate(pivot, pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
        item.Move(delta)
    for m in markers:
        c = m.GetCenter()
        b.gnd_vias.append((pcbnew.ToMM(c.x) - OX, pcbnew.ToMM(c.y) - OY,
                           CL_VIA_D, CL_VIA_DRILL))
        b.board.Remove(m)
    b.created = []


# ======================= antennas + match networks ========================
def t_match(b: Builder, name, node_pt, feed_pt, s1_at, c_at, s2_at, rot, c_rot, node_net):
    """Selector S1 -> shunt C -> series S2 for antenna `name`, pads assigned
    by proximity (node side / antenna side / chain side). Returns the pad
    positions: (s1_node, s1_mid, c_mid, c_gnd, s2_mid, s2_feed)."""
    m = MATCH[name]
    r1, rc, r2 = m["refs"]
    mid, feed = f"M_{name}", f"FEED_{name}"
    n1 = b.two_pin(r1, *R0603, *s1_at, rot, m["s1"], node_pt, node_net, mid)
    n2 = b.two_pin(r2, *L0603, *s2_at, rot, m["s2"], feed_pt, feed, mid)
    nc = b.two_pin(rc, *C0603, *c_at, c_rot, m["c"], s1_at, mid, "GND")
    return (b.P(r1, n1[0]), b.P(r1, n1[1]), b.P(rc, nc[0]), b.P(rc, nc[1]),
            b.P(r2, n2[1]), b.P(r2, n2[0]))


def ifa(b: Builder, name, short_ref, short_at, short_rot, gnd_dxdy):
    """Draw antenna `name` and its 0R shorting jumper."""
    a = ag.antenna(name)
    feed = f"FEED_{name}"
    b.track(feed, a["feed"], ANT_W)
    parts = ag.arm_parts(name)
    ld = ag.load(name)
    if not ld:
        b.track(feed, parts[0], ANT_W)
    else:                             # series tuning element in the arm
        far = f"ARM_{name}"
        lref = MATCH[name]["tune_ref"]
        b.two_pin(lref, *L0603, *ld["at"], 90 if ld["axis"] == "y" else 0,
                  MATCH[name]["tune"], parts[0][-1], feed, far)
        pf = next(p.GetNumber() for p in b.fps[lref].Pads() if p.GetNetname() == feed)
        pa = next(p.GetNumber() for p in b.fps[lref].Pads() if p.GetNetname() == far)

        def pull_back(pl, at_end, d=1.0):
            """Shorten a polyline by d mm at its start or end."""
            pl = list(pl)
            (x0, y0), (x1, y1) = (pl[-2], pl[-1]) if at_end else (pl[1], pl[0])
            L = math.hypot(x1 - x0, y1 - y0)
            q = (x1 - (x1 - x0) * d / L, y1 - (y1 - y0) * d / L)
            if at_end:
                pl[-1] = q
            else:
                pl[0] = q
            return pl

        p0 = pull_back(parts[0], True)
        p1 = pull_back(parts[1], False)
        b.track(feed, p0, ANT_W)
        b.track(feed, [p0[-1], (lref, pf)], 0.8)
        b.track(far, p1, ANT_W)
        b.track(far, [(lref, pa), p1[0]], 0.8)
    s_end = a["short"][1]
    b.two_pin(short_ref, *R0603, *short_at, short_rot,
              "0R" if ag.shorted(name) else "DNP", s_end, feed, "GND")
    pads = sorted(b.fps[short_ref].Pads(), key=lambda p: p.GetNetname() != feed)
    ant_pad, gnd_pad = pads[0].GetNumber(), pads[1].GetNumber()
    b.track(feed, [(short_ref, ant_pad), s_end], ANT_W)
    b.gnd_stub(short_ref, gnd_pad, *gnd_dxdy)
    return a


def build_antennas(b: Builder):
    # ---- radio A: node N_A = (29, 32.5) --------------------------------
    na, node = "ANT_A", (29.0, 32.5)
    a433 = ifa(b, "433", "R401", (23.0, 21.3), 90, (0, 1.3))
    f433 = a433["feed"][0]
    p = t_match(b, "433", node, (29.0, 20.0), (29.0, 26.0), (31.3, 24.3), (29.0, 22.6),
                90, 0, na)
    b.track(na, [p[0], node], RF_SEL)
    b.track("M_433", [p[1], p[4]], RF_SEL)
    b.track("M_433", [p[2], (29.0, p[2][1])], RF_SEL)
    rc = MATCH["433"]["refs"][1]
    gp = next(x.GetNumber() for x in b.fps[rc].Pads() if x.GetNetname() == "GND")
    b.gnd_stub(rc, gp, 1.3, 0)
    b.track("FEED_433", [p[5], (29.0, 20.6), f433], RF_SEL)

    a315 = ifa(b, "315", "R402", (23.3, 28.5), 0, (1.3, 0))
    f315 = a315["feed"][0]
    fy = f315[1]
    p = t_match(b, "315", node, (22.0, fy), (27.2, fy), (25.5, fy + 2.3), (24.0, fy),
                0, 90, na)
    b.track(na, [p[0], node], RF_SEL)
    b.track("M_315", [p[1], p[4]], RF_SEL)
    b.track("M_315", [p[2], (p[2][0], fy)], RF_SEL)
    rc = MATCH["315"]["refs"][1]
    gp = next(x.GetNumber() for x in b.fps[rc].Pads() if x.GetNetname() == "GND")
    b.gnd_stub(rc, gp, 0, 1.3)
    b.track("FEED_315", [p[5], f315], RF_SEL)

    ya = b.P("C125", "2")
    b.track(na, [("C125", "2"), (ya[0] - 1.0, ya[1])], RF_IN)
    b.track(na, [(ya[0] - 1.0, ya[1]), node], RF_50)
    b.two_pin("R403", *R0603, 27.0, 35.2, 90, "DNP", node, na, "EXT_A")
    ext_pad = next(x.GetNumber() for x in b.fps["R403"].Pads() if x.GetNetname() == "EXT_A")
    node_pad = next(x.GetNumber() for x in b.fps["R403"].Pads() if x.GetNetname() == na)
    b.track(na, [node, ("R403", node_pad)], RF_SEL)
    b.fp("J1", "nano_every_cc1101", "SMA_BWSMA-KE-P001_EdgeMount", 27.0, BOARD - 2.7,
         270, "SMA", {"1": "EXT_A", "2": "GND"})
    b.fp("H1", "TestPoint", "TestPoint_THTPad_D2.0mm_Drill1.0mm", 27.0, 60.0, 0, "wire",
         {"1": "EXT_A"})
    b.track("EXT_A", [("R403", ext_pad), ("H1", "1"), ("J1", "1")], RF_50)

    # ---- radio B: node N_B = (80, yb) ----------------------------------
    nb = "ANT_B"
    yb = b.P("C625", "2")[1]
    nodeb = (80.0, yb)
    b.track(nb, [("C625", "2"), nodeb], RF_IN)

    a868 = ifa(b, "868", "R404", (80.7, ag.antenna("868")["short"][0][1]), 0, (-1.3, 0))
    f868 = a868["feed"][0]
    p = t_match(b, "868", nodeb, (82.0, f868[1]), (80.0, 30.3), (77.6, 28.7), (80.0, 27.1),
                90, 0, nb)
    b.track(nb, [nodeb, p[0]], RF_50)
    b.track("M_868", [p[1], p[4]], RF_SEL)
    b.track("M_868", [p[2], (80.0, p[2][1])], RF_SEL)
    rc = MATCH["868"]["refs"][1]
    gp = next(x.GetNumber() for x in b.fps[rc].Pads() if x.GetNetname() == "GND")
    b.gnd_stub(rc, gp, -1.3, 0)
    b.track("FEED_868", [p[5], (80.0, f868[1]), f868], RF_SEL)

    a915 = ifa(b, "915", "R405", (80.7, ag.antenna("915")["short"][0][1]), 0, (0, 1.5))
    f915 = a915["feed"][0]
    p = t_match(b, "915", nodeb, (82.0, f915[1]), (80.0, f915[1] - 4.7),
                (77.6, f915[1] - 3.1), (80.0, f915[1] - 1.5), 90, 0, nb)
    b.track(nb, [nodeb, p[0]], RF_50)
    b.track("M_915", [p[1], p[4]], RF_SEL)
    b.track("M_915", [p[2], (80.0, p[2][1])], RF_SEL)
    rc = MATCH["915"]["refs"][1]
    gp = next(x.GetNumber() for x in b.fps[rc].Pads() if x.GetNetname() == "GND")
    b.gnd_stub(rc, gp, -1.3, 0)
    b.track("FEED_915", [p[5], (80.0, f915[1]), f915], RF_SEL)

    b.two_pin("R406", *R0603, 78.0, yb + 2.3, 90, "DNP", nodeb, nb, "EXT_B")
    ext_pad = next(x.GetNumber() for x in b.fps["R406"].Pads() if x.GetNetname() == "EXT_B")
    node_pad = next(x.GetNumber() for x in b.fps["R406"].Pads() if x.GetNetname() == nb)
    b.track(nb, [(79.0, yb), (78.0, yb + 1.0), ("R406", node_pad)], RF_SEL)
    b.fp("J2", "nano_every_cc1101", "SMA_BWSMA-KE-P001_EdgeMount", 73.0, BOARD - 2.7,
         270, "SMA", {"1": "EXT_B", "2": "GND"})
    b.fp("H2", "TestPoint", "TestPoint_THTPad_D2.0mm_Drill1.0mm", 73.0, 70.0, 0, "wire",
         {"1": "EXT_B"})
    ey = b.P("R406", ext_pad)[1]
    b.track("EXT_B", [("R406", ext_pad), (73.0, ey + 5.0), ("H2", "1"), ("J2", "1")], RF_50)


# ======================= host side =========================================
def build_host(b: Builder):
    b.fp("A1", "Module", "Arduino_Nano", NANO_X0, NANO_Y0, 0, "Arduino Nano Every",
         {str(n): v[0] for n, v in NANO_PINS.items()})
    b.fp("J3", "Connector_PinHeader_2.54mm", "PinHeader_1x15_P2.54mm_Vertical",
         NANO_X0 - 3.4, NANO_Y0, 0, "Breakout 1-15",
         {str(n): NANO_PINS[n][0] for n in range(1, 16)})
    b.fp("J4", "Connector_PinHeader_2.54mm", "PinHeader_1x15_P2.54mm_Vertical",
         NANO_X0 + 15.24 + 3.4, NANO_Y0, 0, "Breakout 16-30",
         {str(k): NANO_PINS[31 - k][0] for k in range(1, 16)})
    for n in range(1, 16):
        if NANO_PINS[n][0] != "GND":
            b.track(NANO_PINS[n][0], [("A1", str(n)), ("J3", str(n))], 0.4)
    for k in range(1, 16):
        if NANO_PINS[31 - k][0] != "GND":
            b.track(NANO_PINS[31 - k][0], [("A1", str(31 - k)), ("J4", str(k))], 0.4)

    ux, uy = 50.0, 47.0                     # 3.3 V LDO
    b.fp("U2", "Package_TO_SOT_SMD", "SOT-23-5", ux, uy, 0, "AP2112K-3.3",
         {"1": "+5V", "2": "GND", "3": "+5V", "5": "3V3"})
    b.fp("C5", *C0603, ux - 4.8, uy, 90, "1uF", {"1": "GND", "2": "+5V"})
    b.fp("C6", "Capacitor_SMD", "C_0805_2012Metric", ux + 3.8, uy, 90, "10uF",
         {"1": "GND", "2": "3V3"})
    y1, y3 = b.P("U2", "1")[1], b.P("U2", "3")[1]
    b.track("+5V", [("U2", "1"), (ux - 3.0, y1), (ux - 3.0, y3), ("U2", "3")], PWR)
    b.track("+5V", [(ux - 3.0, y1), ("C5", "2")], PWR)
    b.track("3V3", [("U2", "5"), (b.P("C6", "2")[0], b.P("U2", "5")[1]), ("C6", "2")], PWR)
    b.track("GND", [("U2", "2"), (ux, uy)], TRACK)
    b.gnd_vias.append((ux, uy, VIA_D, VIA_DRILL))
    b.gnd_stub("C5", "1", 0, 1.3)
    b.gnd_stub("C6", "1", 0, 1.3)

    b.fp("D1", "LED_SMD", "LED_0603_1608Metric", 44.0, 52.0, 0, "green",
         {"1": "GND", "2": "LED_A"})
    b.fp("R1", *R0603, 47.0, 52.0, 0, "1k", {"1": "LED_A", "2": "3V3"})
    b.track("LED_A", [("D1", "2"), ("R1", "1")])
    b.gnd_stub("D1", "1", 0, 1.4)

    txs = {"2": "3V3", "10": "3V3", "11": "GND", "19": "+5V"}
    for ch, (a, bb) in TXS.items():
        txs[TXS_A_PIN[ch]] = a
        txs[TXS_B_PIN[ch]] = bb
    tx, ty = 50.0, 36.0
    b.fp("U3", "Package_SO", "TSSOP-20_4.4x6.5mm_P0.65mm", tx, ty, 270, "TXS0108EPWR", txs)
    b.fp("C7", *C0603, tx + 2.275, ty - 5.7, 90, "100nF", {"1": "3V3", "2": "GND"})
    b.fp("C8", *C0603, tx + 2.275, ty + 5.7, 90, "100nF", {"1": "GND", "2": "+5V"})
    b.track("3V3", [("U3", "2"), ("C7", "1")], PWR)
    b.track("+5V", [("U3", "19"), ("C8", "2")], PWR)
    b.gnd_stub("C7", "2", 0, -1.3)
    b.gnd_stub("C8", "1", 0, 1.3)
    x, y = b.P("U3", "11")
    b.track("GND", [("U3", "11"), (x, y + 1.0), (x - 1.0, y + 1.6)], TRACK)
    b.gnd_vias.append((x - 1.0, y + 1.6, VIA_D, VIA_DRILL))

    # radio B GDO2 has no free level-shifter channel: 3.3 V test pad
    b.fp("TP1", "TestPoint", "TestPoint_Pad_D1.5mm", 58.5, 40.0, 0, "GDO2_B",
         {"1": "GDO2_B"})

    for ref, (x, y) in {"H3": (45.0, 24.0), "H4": (68.0, 24.0),
                        "H5": (30.5, 88.0), "H6": (69.5, 88.0)}.items():
        b.fp(ref, "MountingHole", "MountingHole_3.2mm_M3", x, y, 0, "M3", {})


# ======================= main ==============================================
def main() -> int:
    b = Builder()
    build_radio(b, "A", 0, "433", RADIO_A_AT, 90)
    build_radio(b, "B", 500, "868", RADIO_B_AT, 0)
    build_antennas(b)
    build_host(b)
    board = b.board

    edge = pcbnew.PCB_SHAPE(board)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(b.pt(0, 0))
    edge.SetEnd(b.pt(BOARD, BOARD))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(FromMM(0.1))
    board.Add(edge)
    b.ds.SetAuxOrigin(b.pt(0, BOARD))
    b.ds.SetGridOrigin(b.pt(0, BOARD))

    # ---- autoroute --------------------------------------------------------
    keepouts = []

    def keepout(x0, y0, x1, y1, layers=(pcbnew.F_Cu, pcbnew.B_Cu)):
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowCopperPour(False)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        ls = pcbnew.LSET()
        for layer in layers:
            ls.AddLayer(layer)
        z.SetLayerSet(ls)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
            ol.Append(FromMM(OX + x), FromMM(OY + y))
        board.Add(z)
        keepouts.append(z)

    keepout(0, 0, BOARD, GND_Y0 + 0.5)                  # antenna strips
    keepout(0, 0, GND_X0 + 0.5, BOARD)
    keepout(GND_X1 - 0.5, 0, BOARD, BOARD)
    keepout(GND_X0, GND_Y0, 38.5, 39.0)                  # radio A RF + matches
    keepout(25.0, 34.0, 29.0, BOARD)                     # EXT_A line
    keepout(68.0, 40.5, GND_X1, 52.0)                    # radio B RF
    keepout(76.0, GND_Y0, GND_X1, BOARD)                 # radio B lines + matches
    keepout(71.0, 46.0, 79.0, BOARD)                     # EXT_B line

    for x, y, d, drill in b.gnd_vias:
        b.via("GND", x, y, d, drill)
    gnd_nc = pcbnew.NETCLASS("GND_PLANE")
    gnd_nc.SetClearance(FromMM(0.15))
    gnd_nc.SetTrackWidth(FromMM(PWR))
    b.ds.m_NetSettings.m_NetClasses["GND_PLANE"] = gnd_nc

    dsn = os.path.join(HERE, "route.dsn")
    ses = os.path.join(HERE, "route.ses")
    if not os.environ.get("NOROUTE"):
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            raise SystemExit("DSN export failed")
        text = open(dsn).read()
        text = re.sub(r"(\(class kicad_default[^\n]*?) GND( |\n)", r"\1\2", text, count=1)
        text = text.replace("(class GND_PLANE", "(class GND_PLANE GND", 1)
        open(dsn, "w").write(text)
        subprocess.run(["xvfb-run", "-a", "java", "-jar", FREEROUTING, "-de", dsn, "-do", ses,
                        "-mp", "40", "-mt", "1", "-inc", "GND_PLANE"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)
        import_ses(board, ses, b.net)
        os.remove(dsn)
        os.remove(ses)
    for z in keepouts:
        board.Remove(z)
    drop_dangling(board)

    # ---- ground ------------------------------------------------------------
    stitch_ground(board, lambda x, y: b.via("GND", x, y))
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(b.net("GND"))
        z.SetLocalClearance(FromMM(0.2))
        z.SetMinThickness(FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in [(GND_X0, GND_Y0), (GND_X1, GND_Y0), (GND_X1, BOARD), (GND_X0, BOARD)]:
            ol.Append(FromMM(OX + x), FromMM(OY + y))
        board.Add(z)

    silkscreen(b)

    pcbnew.SaveBoard(OUT, board)
    board = pcbnew.LoadBoard(OUT)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(OUT, board)
    print(f"wrote {OUT}")
    return 0


# ======================= helpers ============================================
def _sexpr(text):
    """Tiny s-expression reader for Specctra session files."""
    tokens = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)
    stack = [[]]
    for tok in tokens:
        if tok == "(":
            stack.append([])
        elif tok == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok.strip('"'))
    return stack[0][0]


def import_ses(board, path, net):
    """Add Freerouting's wires and vias (Specctra .ses) to the board.
    (pcbnew.ImportSpecctraSES only works inside the KiCad GUI.)"""
    ses = _sexpr(open(path).read())
    routes = next(x for x in ses if isinstance(x, list) and x[0] == "routes")
    res = next(x for x in routes if isinstance(x, list) and x[0] == "resolution")
    scale = {"um": 1e-3, "mm": 1.0, "mil": 0.0254}[res[1]] / float(res[2])
    netout = next(x for x in routes if isinstance(x, list) and x[0] == "network_out")
    n_w = n_v = 0

    def xy(x, y):
        return VECTOR2I(FromMM(float(x) * scale), FromMM(-float(y) * scale))

    for n in netout[1:]:
        for item in n[2:]:
            if item[0] == "wire":
                p = item[1]
                layer = pcbnew.F_Cu if p[1] == "F.Cu" else pcbnew.B_Cu
                pts = [xy(p[i], p[i + 1]) for i in range(3, len(p), 2)]
                for a, c in zip(pts, pts[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(a)
                    t.SetEnd(c)
                    t.SetWidth(FromMM(float(p[2]) * scale))
                    t.SetLayer(layer)
                    t.SetNet(net(n[1]))
                    board.Add(t)
                    n_w += 1
            elif item[0] == "via":
                m = re.search(r"_(\d+):(\d+)_um", item[1])
                v = pcbnew.PCB_VIA(board)
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetPosition(xy(item[2], item[3]))
                v.SetWidth(FromMM(int(m.group(1)) / 1000))
                v.SetDrill(FromMM(int(m.group(2)) / 1000))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(net(n[1]))
                board.Add(v)
                n_v += 1
    print(f"imported {n_w} track segments, {n_v} vias from Freerouting")


def drop_dangling(board):
    """Remove signal vias the router left with copper on one layer only (it
    reached the pad stub on the top layer instead)."""
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        if v.GetNetname() in ("GND", ""):
            continue
        p = v.GetPosition()
        layers = {t.GetLayer() for t in tracks
                  if t.GetNetCode() == v.GetNetCode() and p in (t.GetStart(), t.GetEnd())}
        if len(layers) < 2:
            board.Remove(v)


def silkscreen(b: Builder):
    board = b.board

    def text(s, x, y, size=1.0, rot=0, layer=pcbnew.F_SilkS,
             just=pcbnew.GR_TEXT_H_ALIGN_CENTER):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(b.pt(x, y))
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(max(0.15, size * 0.15)))
        t.SetTextAngleDegrees(rot)
        t.SetMirrored(layer == pcbnew.B_SilkS)
        t.SetHorizJustify(just)
        board.Add(t)

    def line(x0, y0, x1, y1, w=0.15):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(b.pt(x0, y0))
        s.SetEnd(b.pt(x1, y1))
        s.SetLayer(pcbnew.F_SilkS)
        s.SetWidth(FromMM(w))
        board.Add(s)

    for n in range(1, 16):
        x, y = b.P("J3", str(n))
        text(NANO_PINS[n][1], x - 1.6, y, just=pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    for k in range(1, 16):
        x, y = b.P("J4", str(k))
        text(NANO_PINS[31 - k][1], x + 1.6, y, just=pcbnew.GR_TEXT_H_ALIGN_LEFT)
    text("USB", 50.0, 97.8)
    text("NANO EVERY", 50.0, 75.0, size=1.5, rot=90)

    text("433 MHz ANTENNA - radio A", 60.0, 9.0, size=1.2)
    text("315 MHz ANTENNA - radio A (315 BOM)", 17.5, 66.0, size=1.2, rot=90)
    text("868 MHz - radio B", 87.5, 38.0, size=1.0, rot=90)
    text("915 MHz - radio B", 87.5, 79.0, size=1.0, rot=90)
    for name in ag.NAMES:            # trim ticks: 2 mm apart, last 10 mm of each arm
        (xa, ya), (xb, yb) = ag.antenna(name)["arm"][-2:]
        L = math.hypot(xb - xa, yb - ya)
        ux, uy = (xb - xa) / L, (yb - ya) / L
        for i in range(6):
            px, py = xb - ux * 2.0 * i, yb - uy * 2.0 * i
            line(px - uy * 1.2, py + ux * 1.2, px - uy * 2.2, py + ux * 2.2)
    text("SMA A", 27.0, 88.0, rot=90)
    text("SMA B", 73.0, 88.0, rot=90)
    text("WIRE A", 27.0, 65.0, rot=90)
    text("WIRE B", 73.0, 75.0, rot=90)
    text("GDO2_B", 58.5, 42.2)
    text("3V3", 44.0, 54.0)

    rows = [
        "NANO EVERY + 2x CC1101   300-928 MHz",
        "2-layer  100 x 100 mm  v1.0",
        "",
        "ANTENNA SELECT - fit ONE selector per radio",
        "radio A: 433 R301 | 315 R311 | SMA/wire R403",
        "radio B: 868 R321 | 915 R331 | SMA/wire R406",
        "IFA shorts R401 R402 R404 R405: always 0R",
        "ANY FREQUENCY 300-348/387-464/779-928 MHz:",
        "fit tune L40x + R3x1/C3x1/L3x1 per tuning.md",
        "whip for SMA/wire: L(mm) = 71250 / f(MHz)",
        "",
        "SPI: D13 SCK  D11 MOSI  D12 MISO",
        "radio A: CSn D10  GDO0 D2  GDO2 D3",
        "radio B: CSn D9   GDO0 D4  GDO2 pad",
    ]
    for i, r in enumerate(rows):
        if r:
            text(r, 52.0, 28.5 + i * 1.8, size=1.0, layer=pcbnew.B_SilkS)


def stitch_ground(board, add_via, pitch=4.0, clearance=0.3):
    """GND vias on a grid (+ fences along the antenna edges) wherever they
    clear every other-net object and stay out from under parts."""
    r = VIA_D / 2

    def mm(v):
        return pcbnew.ToMM(v)

    obstacles = []
    for fp in board.GetFootprints():
        bb = fp.GetBoundingBox(False, False)
        obstacles.append(("keepout", (mm(bb.GetX()) - OX - 0.3, mm(bb.GetY()) - OY - 0.3,
                                      mm(bb.GetRight()) - OX + 0.3,
                                      mm(bb.GetBottom()) - OY + 0.3), None))
        for pad in fp.Pads():
            bx = pad.GetBoundingBox()
            obstacles.append(("rect", (mm(bx.GetX()) - OX, mm(bx.GetY()) - OY,
                                       mm(bx.GetRight()) - OX, mm(bx.GetBottom()) - OY),
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
        return math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1))

    def dist_seg(x, y, ax, ay, bx, by):
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        u = 0 if L2 == 0 else max(0, min(1, ((x - ax) * vx + (y - ay) * vy) / L2))
        return math.hypot(x - (ax + u * vx), y - (ay + u * vy))

    def ok(x, y):
        for kind, g, n in obstacles:
            if kind == "keepout":
                if g[0] < x < g[2] and g[1] < y < g[3]:
                    return False
            elif kind == "circle" and n == "GND":
                if math.hypot(x - g[0], y - g[1]) < r + g[2] + 0.3:
                    return False
            elif n == "GND":
                continue
            elif kind == "rect" and dist_rect(x, y, *g) < r + clearance:
                return False
            elif kind == "circle" and math.hypot(x - g[0], y - g[1]) < r + g[2] + clearance:
                return False
            elif kind == "seg" and dist_seg(x, y, *g[:4]) < r + g[4] + clearance:
                return False
        return True

    cands = [(GND_X0 + 1.0 + 2.5 * i, GND_Y0 + 1.0) for i in range(25)]
    cands += [(GND_X0 + 1.0, GND_Y0 + 1.0 + 2.5 * i) for i in range(33)]
    cands += [(GND_X1 - 1.0, GND_Y0 + 1.0 + 2.5 * i) for i in range(33)]
    cands += [(GND_X0 + 1.0 + 2.5 * i, BOARD - 1.0) for i in range(25)]
    cands += [(GND_X0 + 2.5 + pitch * ix, GND_Y0 + 3.0 + pitch * iy)
              for iy in range(20) for ix in range(15)]
    placed = []
    for x, y in cands:
        if not (GND_X0 + 0.8 <= x <= GND_X1 - 0.8 and GND_Y0 + 0.8 <= y <= BOARD - 0.8):
            continue
        if ok(x, y) and all(math.hypot(x - px, y - py) >= 1.5 for px, py in placed):
            add_via(x, y)
            placed.append((x, y))
            obstacles.append(("circle", (x, y, r), "GND"))
    return placed


if __name__ == "__main__":
    raise SystemExit(main())
