#!/usr/bin/env python3
"""Generate nano_every_cc1101.kicad_pcb: a compact 70 x 45 mm, 2-layer
carrier for an Arduino Nano Every with two TI CC1101 radios:

  radio A (U1)   : 315 / 433 MHz front end (433 MHz BOM fitted)
                   -> coil antennas AE1 433 MHz (selected) + AE2 315 MHz,
                      optional SMA J1
  radio B (U501) : 868 / 915 MHz front end
                   -> coil antennas AE3 868 MHz (selected) + AE4 915 MHz,
                      optional SMA J2

The antennas are helical spring ("coil") antennas standing up from the
board edge, JLCPCB-assembled through-hole parts. Every antenna branch
starts at the radio's 50 ohm bus with a series selector (fit it to use that
antenna), then a shunt part and a second series part: a T-match right at
the coil for retuning (default: 0R / not fitted / 0R). All four coils are
fitted; moving one 0R selector per radio switches band.

Run with KiCad 7's Python (`/usr/bin/python3 gen_board.py`). Steps:
  1. place parts; hand-route both CC1101 clusters (radio A = the
     boards/cc1101-mini layout; radio B = the same core with TI's 868/915 MHz
     balun), every RF line and match network, the LDO/level-shifter power
     stubs and the Nano breakout links
  2. autoroute the remaining digital/power nets with Freerouting (GND is
     excluded: it lands on the pours through its own vias)
  3. stitch and pour ground on both layers (clear of the coils), save

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
W, H = 70.0, 45.0                       # board outline
COIL_X = 66.3                           # coil antenna column (right edge)
STRIP_X = 63.0                          # no ground right of this beside the coils
# ground pour outline: whole board except the two coil strips (the SMA jacks
# in between keep their ground)
POUR = [(0, 0), (STRIP_X, 0), (STRIP_X, 15.3), (W, 15.3), (W, 29.7), (STRIP_X, 29.7),
        (STRIP_X, H), (0, H)]

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
    "C41": (*C0402, 3.2, 7.8, 90, "100nF", {"1": "GND", "2": "3V3"}),
    "C51": (*C0402, 4.15, 7.95, 90, "100nF", {"1": "GND", "2": "DCOUPL*"}),   # body 0.1 mm clear of U
    "R171": (*R0402, 7.6, 2.3, 90, "56k 1%", {"1": "RBIAS*", "2": "GND"}),
    "C181": (*C0402, 5.75, 1.3, 0, "100nF", {"1": "GND", "2": "3V3"}),
    "C151": (*C0402, 8.85, 2.3, 90, "100nF", {"1": "3V3", "2": "GND"}),
    "C111": (*C0402, 9.2, 8.95, 90, "100nF", {"1": "GND", "2": "3V3"}),
}
CORE_GND_ESCAPE = {
    "C181": (4.8, 0.75), "R171": (7.6, 1.2), "C151": (8.85, 1.2),
    "C41": (3.2, 9.0), "C51": (3.2, 9.0), "C111": (9.75, 9.6),
    "C101": (8.75, 12.0), "C81": (3.1, 11.68),
}

# 315/433 MHz balun + LC filter (SWRS061I Fig. 10, 433 MHz values)
RF_433 = {
    "C131": (*C0402, 9.85, 3.85, 90, "3.9pF", {"1": "RF_N*", "2": "GND"}),
    "L131": (*L0402, 10.35, 5.55, 0, "27nH", {"1": "RF_N*", "2": "RF_J*"}),
    "C121": (*C0402, 10.35, 6.95, 0, "3.9pF", {"1": "RF_P*", "2": "RF_J*"}),
    "L121": (*L0402, 10.35, 8.45, 90, "27nH", {"1": "RF_L121*", "2": "RF_P*"}),
    "C124": (*C0402, 10.35, 10.6, 90, "330pF", {"1": "GND", "2": "RF_L121*"}),
    "L122": (*L0402, 12.25, 6.25, 0, "22nH", {"1": "RF_J*", "2": "RF_F1*"}),
    "C122": (*C0402, 12.75, 7.95, 90, "8.2pF", {"1": "GND", "2": "RF_F1*"}),
    "L123": (*L0402, 14.15, 6.25, 0, "27nH", {"1": "RF_F1*", "2": "RF_F2*"}),
    "C123": (*C0402, 14.65, 7.95, 90, "5.6pF", {"1": "GND", "2": "RF_F2*"}),
    "C125": (*C0402, 16.0, 5.45, 90, "330pF", {"1": "RF_F2*", "2": "ANT*"}),
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

RADIO_A_AT, RADIO_B_AT = (38.5, 7.0), (38.5, 36.5)     # U centres, both rot 0

NANO_X0, NANO_Y0 = 8.5, 5.5           # Nano pad 1 (rotation 0: USB at the bottom edge)
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
    T("3V3", [("U1", "4"), (3.2, 6.5), ("C41", "2")], 0.2); V("3V3", 3.2, 6.5)
    T("DCOUPL*", [("U1", "5"), (4.15, 7.0), ("C51", "2")], cp)
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


# ======================= coil antennas + match networks ===================
# band -> radio, (selector, shunt, series) refs, coil ref, row y, selected, part.
# All four coils are fitted; each radio's selector picks one (radio A's 315 MHz
# coil also needs the 315 MHz front-end BOM). Coils sit 8.7 mm apart so the
# unselected one loads the active one as little as the board allows.
COILS = {
    "433": ("A", ("R301", "C301", "L301"), "AE1", 3.3, True, "BW433SNX21-5W2"),
    "315": ("A", ("R311", "C311", "L311"), "AE2", 12.0, False, "BW315SNX39-6W3"),
    "915": ("B", ("R331", "C331", "L331"), "AE4", 33.0, False, "BW915SNX17-5W2"),
    "868": ("B", ("R321", "C321", "L321"), "AE3", 41.7, True, "BW868SNX20-5Z6"),
}
BUS_X = {"A": 51.0, "B": 54.0}          # each radio's vertical 50 ohm bus
SMA = {"A": ("R403", "J1", 18.8), "B": ("R406", "J2", 26.2)}


def coil_branch(b: Builder, band):
    radio, (r1, rc, r2), ae, y, selected, part = COILS[band]
    bx = BUS_X[radio]
    bus, mid, feed = f"ANT_{radio}", f"M_{band}", f"FEED_{band}"
    s1x, cx, s2x = bx + 2.2, bx + 4.6, bx + 7.0
    up = -1 if y > H - 6 else 1          # shunt below the line, above it on the bottom row
    n1 = b.two_pin(r1, *R0603, s1x, y, 0, "0R" if selected else "DNP", (bx, y), bus, mid)
    n2 = b.two_pin(r2, *L0603, s2x, y, 0, "0R", (s2x - 1, y), mid, feed)
    nc = b.two_pin(rc, *C0603, cx, y + 1.3 * up, 90, "DNP", (cx, y), mid, "GND")
    b.fp(ae, "nano_every_cc1101", "Coil_Spring_D5.5_THT", COIL_X, y, 0, part, {"1": feed})
    b.track(bus, [(bx, y), (r1, n1[0])], RF_50)
    b.track(mid, [(r1, n1[1]), (r2, n2[0])], RF_SEL)
    b.track(mid, [(rc, nc[0]), (cx, y)], RF_SEL)
    b.track(feed, [(r2, n2[1]), (ae, "1")], RF_SEL)
    b.gnd_stub(rc, nc[1], 0, 1.2 * up)


def build_rf(b: Builder):
    for radio in ("A", "B"):
        bx = BUS_X[radio]
        rows = [v[3] for v in COILS.values() if v[0] == radio]
        ax, ay = b.P("C125" if radio == "A" else "C625", "2")      # balun output (ANT_x)
        b.track(f"ANT_{radio}", [(ax, ay), (bx, ay)], RF_IN)
        sel, jack, jy = SMA[radio]
        # SMA selector right at the bus end, so an unused jack line is no stub
        sy = max(rows) + 2.3 if radio == "A" else min(rows) - 2.3
        b.two_pin(sel, *R0603, bx, sy, 90, "DNP", (bx, sy - 1 if radio == "A" else sy + 1),
                  f"ANT_{radio}", f"SMA_{radio}")
        near = next(p.GetNumber() for p in b.fps[sel].Pads() if p.GetNetname() == f"ANT_{radio}")
        far = next(p.GetNumber() for p in b.fps[sel].Pads() if p.GetNetname() == f"SMA_{radio}")
        b.track(f"ANT_{radio}", [(bx, min(rows)), (bx, max(rows))], RF_50)
        b.track(f"ANT_{radio}", [(bx, max(rows) if radio == "A" else min(rows)), (sel, near)],
                RF_50)
        b.fp(jack, "nano_every_cc1101", "SMA_BWSMA-KE-P001_EdgeMount", W - 2.7, jy, 0, "SMA",
             {"1": f"SMA_{radio}", "2": "GND"})
        fx, fy = b.P(sel, far)
        ly = fy + 1.7 if radio == "A" else fy - 1.6
        b.track(f"SMA_{radio}", [(fx, fy), (fx, ly), (61.5, ly), (61.5 + abs(jy - ly), jy),
                                 (jack, "1")], RF_50)
    for band in COILS:
        coil_branch(b, band)


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

    # 3.3 V LDO: XC6206P332MR (SOT-23: 1 GND, 2 VOUT, 3 VIN; 200 mA, JLCPCB
    # basic part). Rotated 180 deg so VIN faces C5 and VOUT faces C6.
    ux, uy = 48.8, 19.5
    b.fp("U2", "Package_TO_SOT_SMD", "SOT-23", ux, uy, 180, "XC6206P332MR",
         {"1": "GND", "2": "3V3", "3": "+5V"})
    b.fp("C5", *C0603, ux - 3.9, uy, 90, "1uF", {"1": "GND", "2": "+5V"})
    b.fp("C6", "Capacitor_SMD", "C_0805_2012Metric", ux + 3.8, uy, 90, "10uF",
         {"1": "GND", "2": "3V3"})
    b.track("+5V", [("U2", "3"), (ux - 3.0, uy), ("C5", "2")], PWR)
    b.track("3V3", [("U2", "2"), (b.P("C6", "2")[0], b.P("U2", "2")[1]), ("C6", "2")], PWR)
    b.track("GND", [("U2", "1"), ("C6", "1")], PWR)     # C6's ground via serves both
    b.gnd_stub("C5", "1", 0, 1.3)
    b.gnd_stub("C6", "1", 0, 1.3)

    b.fp("D1", "LED_SMD", "LED_0603_1608Metric", 46.5, 27.5, 0, "red",
         {"1": "GND", "2": "LED_A"})
    b.fp("R1", *R0603, 49.5, 27.5, 0, "1k", {"1": "LED_A", "2": "3V3"})
    b.track("LED_A", [("D1", "2"), ("R1", "1")])
    b.gnd_stub("D1", "1", 0, 1.4)

    txs = {"2": "3V3", "10": "3V3", "11": "GND", "19": "+5V"}
    for ch, (a, bb) in TXS.items():
        txs[TXS_A_PIN[ch]] = a
        txs[TXS_B_PIN[ch]] = bb
    tx, ty = 40.0, 23.0
    # rot 180: B side (5 V, pins 11-20) faces the Nano, A side (3.3 V) the radios
    b.fp("U3", "Package_SO", "TSSOP-20_4.4x6.5mm_P0.65mm", tx, ty, 180, "TXS0108EPWR", txs)
    vx, vy = b.P("U3", "2")                 # VCCA
    b.fp("C7", *C0603, vx + 2.6, vy, 0, "100nF", {"1": "3V3", "2": "GND"})
    wx, wy = b.P("U3", "19")                # VCCB
    b.fp("C8", *C0603, wx - 2.6, wy, 0, "100nF", {"1": "GND", "2": "+5V"})
    b.track("3V3", [("U3", "2"), ("C7", "1")], PWR)
    b.track("+5V", [("U3", "19"), ("C8", "2")], PWR)
    b.gnd_stub("C7", "2", 0, -1.3)
    b.gnd_stub("C8", "1", 0, 1.3)
    x, y = b.P("U3", "11")
    b.track("GND", [("U3", "11"), (x - 1.4, y)], TRACK)
    b.gnd_vias.append((x - 1.4, y, VIA_D, VIA_DRILL))

    # radio B GDO2 has no free level-shifter channel: 3.3 V test pad
    b.fp("TP1", "TestPoint", "TestPoint_Pad_D1.5mm", 48.0, 23.5, 0, "GDO2_B",
         {"1": "GDO2_B"})


# ======================= main ==============================================
def main() -> int:
    b = Builder()
    build_radio(b, "A", 0, "433", RADIO_A_AT, 0)
    build_radio(b, "B", 500, "868", RADIO_B_AT, 0)
    build_rf(b)
    build_host(b)
    board = b.board
    clip_footprint_silk(board)

    edge = pcbnew.PCB_SHAPE(board)
    edge.SetShape(pcbnew.SHAPE_T_RECT)
    edge.SetStart(b.pt(0, 0))
    edge.SetEnd(b.pt(W, H))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(FromMM(0.1))
    board.Add(edge)
    b.ds.SetAuxOrigin(b.pt(0, H))
    b.ds.SetGridOrigin(b.pt(0, H))

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

    # ground corridors the router must leave open, per radio (mini coords
    # shifted to the cluster): B.Cu from inside the AVDD ring up past the SI
    # via, F.Cu from the C41/C51/C81 ground escapes out to the main pour
    for ux, uy in (RADIO_A_AT, RADIO_B_AT):
        dx, dy = ux - 6.5, uy - 6.0
        keepout(dx + 5.45, max(0.0, dy - 0.3), dx + 6.1, dy + 5.0, (pcbnew.B_Cu,))
        keepout(31.0, dy + 9.4, dx + 3.4, dy + 10.0, (pcbnew.F_Cu,))
    keepout(41.5, 0, W, 16.5)                            # radio A balun, bus, coils
    keepout(50.0, 13.0, W, 17.6)                         # SMA_A line
    keepout(59.0, 13.0, W, 21.5)
    keepout(42.0, 32.0, W, H)                            # radio B balun, bus, coils
    keepout(53.0, 27.5, W, 32.0)                         # SMA_B line
    keepout(59.0, 21.5, W, 32.0)

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
                        "-mp", "120", "-mt", "1", "-inc", "GND_PLANE"], check=True,
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
        for x, y in POUR:
            ol.Append(FromMM(OX + x), FromMM(OY + y))
        board.Add(z)

    silkscreen(b)

    pcbnew.SaveBoard(OUT, board)
    board = pcbnew.LoadBoard(OUT)
    board.BuildConnectivity()
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    for _ in range(4):                       # tie any isolated ground pieces in
        if not join_ground_islands(board):
            break
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(OUT, board)
    # footprints are generated (silk clipped off pads), so a library-sync
    # check is meaningless here; everything else stays at KiCad defaults
    import json
    pro = OUT.replace(".kicad_pcb", ".kicad_pro")
    d = json.load(open(pro))
    d["board"]["design_settings"]["rule_severities"]["lib_footprint_mismatch"] = "ignore"
    json.dump(d, open(pro, "w"), indent=2)
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
    reached the pad stub on the top layer instead), and a hand-placed escape
    stub that only led to such a via. A track counts as touching a via when
    it passes within the via's radius (router ends are rounded on import)."""
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]

    def touches(t, p, r):
        a, c = t.GetStart(), t.GetEnd()
        vx, vy = c.x - a.x, c.y - a.y
        L2 = vx * vx + vy * vy
        u = 0 if L2 == 0 else max(0, min(1, ((p.x - a.x) * vx + (p.y - a.y) * vy) / L2))
        return math.hypot(p.x - (a.x + u * vx), p.y - (a.y + u * vy)) <= r

    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        if v.GetNetname() in ("GND", ""):
            continue
        p, r = v.GetPosition(), v.GetWidth() / 2
        near = [t for t in tracks if t.GetNetCode() == v.GetNetCode() and touches(t, p, r)]
        if len({t.GetLayer() for t in near}) >= 2:
            continue
        board.Remove(v)
        for t in near:                       # stub that only led to this via
            end = t.GetEnd() if touches_pt(t.GetEnd(), p, r) else t.GetStart()
            linked = [o for o in tracks if o is not t and o.GetNetCode() == t.GetNetCode()
                      and o.GetLayer() == t.GetLayer() and touches(o, end, t.GetWidth() / 2)]
            on_pad = any(pad.HitTest(end) for fp in board.GetFootprints() for pad in fp.Pads()
                         if pad.GetNetCode() == t.GetNetCode())
            if not linked and not on_pad:
                board.Remove(t)
                tracks.remove(t)


def touches_pt(q, p, r):
    return math.hypot(q.x - p.x, q.y - p.y) <= r


def join_ground_islands(board, step=0.2):
    """Find GND pour pieces not connected (through vias) to the main pour and
    add a via where such a piece overlaps the other layer's main pour, clear
    of pads and of the fill edges. Returns the number of vias added."""
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    pieces = []                       # (layer, outline)
    for z in board.Zones():
        for L in (pcbnew.F_Cu, pcbnew.B_Cu):
            if z.IsOnLayer(L) and z.GetNetname() == "GND":
                fp = z.GetFilledPolysList(L)
                pieces += [(L, fp.Outline(i)) for i in range(fp.OutlineCount())]
    vset = [set(i for i, v in enumerate(vias) if ol.PointInside(v.GetPosition()))
            for _, ol in pieces]
    parent = list(range(len(pieces)))

    def find(k):
        while parent[k] != k:
            k = parent[k]
        return k
    for i in range(len(pieces)):
        for j in range(i + 1, len(pieces)):
            if vset[i] & vset[j]:
                parent[find(i)] = find(j)
    main = find(max(range(len(pieces)), key=lambda i: abs(pieces[i][1].Area())))
    pads = [(p.GetPosition(), max(p.GetBoundingBox().GetWidth(), p.GetBoundingBox().GetHeight()))
            for fp in board.GetFootprints() for p in fp.Pads()]
    r = FromMM(VIA_D / 2 + 0.15)
    added = 0
    done = set()
    for i, (L, ol) in enumerate(pieces):
        g = find(i)
        if g == main or g in done:
            continue
        others = [pieces[j][1] for j in range(len(pieces))
                  if find(j) == main and pieces[j][0] != L]
        bb = ol.BBox()
        spot = None
        for yy in range(bb.GetY(), bb.GetBottom(), FromMM(step)):
            for xx in range(bb.GetX(), bb.GetRight(), FromMM(step)):
                pt = VECTOR2I(xx, yy)
                ring = [VECTOR2I(int(xx + r * math.cos(t * math.pi / 4)),
                                 int(yy + r * math.sin(t * math.pi / 4))) for t in range(8)]
                if not all(ol.PointInside(q) for q in ring + [pt]):
                    continue
                if not any(all(o.PointInside(q) for q in ring + [pt]) for o in others):
                    continue
                if any(math.dist((pt.x, pt.y), (pp.x, pp.y)) < sz / 2 + FromMM(0.5)
                       for pp, sz in pads):
                    continue
                spot = pt
                break
            if spot:
                break
        if spot:
            v = pcbnew.PCB_VIA(board)
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetPosition(spot)
            v.SetWidth(FromMM(VIA_D))
            v.SetDrill(FromMM(VIA_DRILL))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(board.FindNet("GND"))
            board.Add(v)
            added += 1
            done.add(g)
            print(f"ground island joined with a via at "
                  f"({pcbnew.ToMM(spot.x) - OX:.2f}, {pcbnew.ToMM(spot.y) - OY:.2f})")
    return added


def clip_footprint_silk(board, margin=0.12):
    """Drop footprint silkscreen strokes that touch a pad (their own or a
    neighbour's): fabs clip them anyway, and KiCad flags them as silk over
    copper / silk overlap. Keeps the rest of each outline."""
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            pads.append((pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()),
                         pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()),
                         pad.IsOnLayer(pcbnew.F_Cu), pad.IsOnLayer(pcbnew.B_Cu)))

    def samples(item):
        sh = item.GetShape()
        if sh == pcbnew.SHAPE_T_SEGMENT:
            a, c = item.GetStart(), item.GetEnd()
            n = max(2, int(math.dist((a.x, a.y), (c.x, c.y)) / FromMM(0.05)))
            return [(a.x + (c.x - a.x) * i / n, a.y + (c.y - a.y) * i / n) for i in range(n + 1)]
        if sh == pcbnew.SHAPE_T_CIRCLE:
            cx, cy, r = item.GetCenter().x, item.GetCenter().y, item.GetRadius()
            return [(cx + r * math.cos(t / 90 * math.pi), cy + r * math.sin(t / 90 * math.pi))
                    for t in range(180)]
        if sh == pcbnew.SHAPE_T_ARC:
            return [(p.x, p.y) for p in (item.GetStart(), item.GetArcMid(), item.GetEnd())]
        bb = item.GetBoundingBox()
        return [(bb.GetX(), bb.GetY()), (bb.GetRight(), bb.GetBottom())]

    removed = 0
    for fp in board.GetFootprints():
        for item in list(fp.GraphicalItems()):
            layer = item.GetLayer()
            if layer not in (pcbnew.F_SilkS, pcbnew.B_SilkS) or \
                    item.GetClass() not in ("FP_SHAPE", "MGRAPHIC"):
                continue
            front = layer == pcbnew.F_SilkS
            w = pcbnew.ToMM(item.GetWidth()) / 2 + margin
            hit = False
            for px, py in samples(item):
                x, y = pcbnew.ToMM(int(px)), pcbnew.ToMM(int(py))
                if not (OX + 0.3 < x < OX + W - 0.3 and OY + 0.3 < y < OY + H - 0.3):
                    hit = True               # at / past the board edge (Nano overhang)
                    break
                for x0, y0, x1, y1, on_f, on_b in pads:
                    if (on_f if front else on_b) and \
                            math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1)) < w:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                fp.Remove(item)
                removed += 1
    print(f"clipped {removed} footprint silkscreen strokes off pads / the edge")


def silkscreen(b: Builder):
    board = b.board

    def text(s, x, y, size=1.0, rot=0, layer=pcbnew.F_SilkS,
             just=pcbnew.GR_TEXT_H_ALIGN_CENTER):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetPosition(b.pt(x, y))
        t.SetLayer(layer)
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(max(0.12, size * 0.15)))
        t.SetTextAngleDegrees(rot)
        t.SetMirrored(layer == pcbnew.B_SilkS)
        t.SetHorizJustify(just)
        board.Add(t)

    for n in range(1, 16):
        x, y = b.P("J3", str(n))
        text(NANO_PINS[n][1], x - 1.3, y, size=0.8, just=pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    for k in range(1, 16):
        x, y = b.P("J4", str(k))
        text(NANO_PINS[31 - k][1], x + 1.3, y, size=0.8, just=pcbnew.GR_TEXT_H_ALIGN_LEFT)
    cx = NANO_X0 + 7.62
    text("NANO EVERY", cx, NANO_Y0 + 17.8, size=1.5, rot=90)
    text("RADIO A  315/433 MHz", 40.0, 14.4, size=0.8)
    text("RADIO B  868/915 MHz", 40.0, 43.9, size=0.8)
    for band, (radio, refs, ae, y, selected, part) in COILS.items():
        text(band, 61.3, y - 1.4, size=0.8)
    text("SMA A", 58.0, SMA["A"][2] + 0.4, size=0.8)
    text("SMA B", 58.0, SMA["B"][2] - 0.4, size=0.8)
    text("GDO2_B", 49.3, 23.5, size=0.8, just=pcbnew.GR_TEXT_H_ALIGN_LEFT)

    rows = [
        "NANO EVERY + 2x CC1101   300-928 MHz",
        "2-layer  70 x 45 mm  v2.0  coil antennas",
        "",
        "ANTENNA - fit ONE selector per radio",
        "A: 433 coil R301 | 315 coil R311 | SMA R403",
        "B: 868 coil R321 | 915 coil R331 | SMA R406",
        "coil retune: C3x1 shunt, L3x1 series",
        "",
        "SPI: D13 SCK  D11 MOSI  D12 MISO",
        "A: CSn D10  GDO0 D2  GDO2 D3",
        "B: CSn D9   GDO0 D4  GDO2 pad",
    ]
    for i, r in enumerate(rows):
        if r:
            text(r, 45.5, 17.0 + i * 1.5, size=0.8, layer=pcbnew.B_SilkS)


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

    def in_pour(x, y, m=0.8):
        if not (m <= x <= W - m and m <= y <= H - m):
            return False
        return not (x > STRIP_X - m and (y < 15.3 + m or y > 29.7 - m))

    cands = [(1.0 + 2.5 * i, 1.0) for i in range(30)] + [(1.0 + 2.5 * i, H - 1.0) for i in range(30)]
    cands += [(1.0, 1.0 + 2.5 * i) for i in range(20)]
    cands += [(STRIP_X - 1.0, 1.0 + 2.0 * i) for i in range(23)]      # fence beside the coils
    cands += [(W - 1.0, 16.3 + 2.5 * i) for i in range(6)]
    cands += [(2.0 + pitch * ix, 2.5 + pitch * iy) for iy in range(12) for ix in range(18)]
    placed = []
    for x, y in cands:
        if not in_pour(x, y):
            continue
        if ok(x, y) and all(math.hypot(x - px, y - py) >= 1.5 for px, py in placed):
            add_via(x, y)
            placed.append((x, y))
            obstacles.append(("circle", (x, y, r), "GND"))
    return placed


if __name__ == "__main__":
    raise SystemExit(main())

