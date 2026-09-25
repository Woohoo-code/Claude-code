#!/usr/bin/env python3
"""Board-derived outputs (run with KiCad 7's Python after gen_board.py):

  drc_report.txt         KiCad DRC
  ../netlist.md          every net and the pads on it, from the routed board
  ../bom.csv             grouped BOM in pcba-builder's format
  fab/bom-no-nano.csv    purchasing BOM: every fitted part except the Nano Every
  fab/bom-jlcpcb.csv     JLCPCB assembly BOM (fitted parts only)
  fab/cpl-jlcpcb.csv     JLCPCB placement file (fitted SMT parts; SMA jacks, J3/J4 by hand)
"""

import collections
import csv
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, "nano_every_cc1101.kicad_pcb")
sys.path.insert(0, os.path.join(HERE, "..", "antenna"))
from match import MATCH  # noqa: E402

# (footprint name, value) -> (description, manufacturer, MPN, LCSC)
# LCSC numbers and stock substitutes are applied from JLC below.
CAT = {
    ("QFN", "CC1101RGPR"): ("Sub-1 GHz RF transceiver, 300-928 MHz", "Texas Instruments",
                            "CC1101RGPR", ""),
    ("Crystal", "26MHz"): ("Crystal 26 MHz +/-10 ppm CL 16 pF 3225", "YXC", "X322526MQB4SI",
                           "C70573"),
    ("R_0402", "56k 1%"): ("Resistor 56 kohm 1% 0402 (CC1101 RBIAS)", "KOA Speer",
                           "RK73H1ETTP5602F", ""),
    ("C_0402", "27pF"): ("Capacitor 27 pF 5% C0G 0402", "Murata", "GRM1555C1H270JA01D", ""),
    ("C_0402", "100nF"): ("Capacitor 100 nF 10% X7R 16 V 0402", "Murata",
                          "GRM155R71C104KA88D", ""),
    ("C_0402", "3.9pF"): ("Capacitor 3.9 pF +/-0.25 pF C0G 0402", "Murata",
                          "GRM1555C1H3R9CA01D", ""),
    ("C_0402", "8.2pF"): ("Capacitor 8.2 pF +/-0.25 pF C0G 0402", "Murata",
                          "GRM1555C1H8R2CA01D", ""),
    ("C_0402", "5.6pF"): ("Capacitor 5.6 pF +/-0.25 pF C0G 0402", "Murata",
                          "GRM1555C1H5R6CA01D", ""),
    ("C_0402", "330pF"): ("Capacitor 330 pF 5% C0G 0402 (DC block / RF bypass)", "Samsung",
                          "CL05C331JB5NNNC", "C13533"),
    ("C_0402", "1.0pF"): ("Capacitor 1.0 pF +/-0.1 pF C0G 0402", "Murata",
                          "GRM1555C1H1R0BA01D", ""),
    ("C_0402", "1.5pF"): ("Capacitor 1.5 pF +/-0.1 pF C0G 0402", "Murata",
                          "GRM1555C1H1R5BA01D", ""),
    ("C_0402", "3.3pF"): ("Capacitor 3.3 pF +/-0.1 pF C0G 0402", "Murata",
                          "GRM1555C1H3R3BA01D", ""),
    ("C_0402", "100pF"): ("Capacitor 100 pF 5% C0G 0402", "Murata", "GRM1555C1H101JA01D", ""),
    ("C_0402", "12pF"): ("Capacitor 12 pF 5% C0G 0402", "Murata", "GRM1555C1H120JA01D", ""),
    ("L_0402", "27nH"): ("Inductor 27 nH 5% multilayer 0402", "Murata", "LQG15HS27NJ02D", ""),
    ("L_0402", "22nH"): ("Inductor 22 nH 5% multilayer 0402", "Murata", "LQG15HS22NJ02D", ""),
    ("L_0402", "12nH"): ("Inductor 12 nH 5% wire-wound 0402 (868/915 balun)", "Murata",
                         "LQW15AN12NJ00D", ""),
    ("L_0402", "18nH"): ("Inductor 18 nH 5% wire-wound 0402 (868/915 balun)", "Murata",
                         "LQW15AN18NJ00D", ""),
    ("SOT-23", "XC6206P332MR"): ("LDO 3.3 V 200 mA", "Torex", "XC6206P332MR-G", "C5446"),
    ("SOT-23-5", "AP2112K-3.3"): ("LDO 3.3 V 600 mA", "Diodes Inc", "AP2112K-3.3TRG1",
                                  "C51118"),
    ("TSSOP-20", "TXS0108EPWR"): ("8-bit auto-direction level translator 3.3 V <-> 5 V",
                                  "Texas Instruments", "TXS0108EPWR", ""),
    ("C_0603", "1uF"): ("Capacitor 1 uF 10% X5R 0603", "Samsung", "CL10A105KB8NNNC", "C15849"),
    ("C_0805", "10uF"): ("Capacitor 10 uF 10% X5R 25 V 0805", "Samsung", "CL21A106KAYNNNE",
                         "C15850"),
    ("C_0603", "100nF"): ("Capacitor 100 nF 10% X7R 50 V 0603", "Yageo", "CC0603KRX7R9BB104",
                          "C14663"),
    ("R_0603", "1k"): ("Resistor 1 kohm 1% 0603", "UNI-ROYAL", "0603WAF1001T5E", "C21190"),
    ("R_0603", "0R"): ("Jumper 0 ohm 0603", "UNI-ROYAL", "0603WAF0000T5E", "C21189"),
    ("L_0603", "0R"): ("Jumper 0 ohm 0603", "UNI-ROYAL", "0603WAF0000T5E", "C21189"),
    ("LED_0603", "red"): ("LED red 0603", "Hubei KENTO Elec", "KT-0603R", "C2286"),
    ("SMA", "SMA"): ("SMA jack, edge mount (end launch), 50 ohm, 1.6 mm board", "BAT WIRELESS",
                     "BWSMA-KE-P001", "C496550"),
    ("Arduino_Nano", "Arduino Nano Every"): ("Arduino Nano Every (plugs into 2x 1x15 female "
                                             "2.54 mm headers)", "Arduino", "ABX00028", ""),
    ("PinHeader_1x15", None): ("Pin header 1x15 2.54 mm male, straight (breakout)", "Megastar",
                               "ZX-PZ2.54-1-15PZZ", "C7501269"),
}
FP_KEYS = ["QFN", "Crystal", "R_0402", "C_0402", "L_0402", "SOT-23-5", "SOT-23", "TSSOP-20", "C_0603",
           "C_0805", "R_0603", "L_0603", "LED_0603", "SMA", "Arduino_Nano", "PinHeader_1x15"]
NOT_PARTS = ("MountingHole", "TestPoint")

# JLCPCB/LCSC stock check (2026-09-25): LCSC number for every design MPN, or an
# in-stock equivalent (same value, package, C0G/NP0, tolerance) where the
# design part was out of stock. "basic"/"fee-free" = JLCPCB basic or preferred
# extended part (no per-part-type loading fee); the RF match values, RF
# inductors and ICs have no fee-free equivalent and stay extended. design MPN -> (manufacturer, MPN, LCSC)
JLC = {
    "CC1101RGPR": ("Texas Instruments", "CC1101RGPR", "C29953"),
    "RK73H1ETTP5602F": ("UNI-ROYAL", "0402WGF5602TCE", "C25796"),          # fee-free
    "GRM155R71C104KA88D": ("Samsung", "CL05B104KO5NNNC", "C1525"),           # basic
    "GRM1555C1H270JA01D": ("FH", "0402CG270J500NT", "C1557"),               # fee-free
    "GRM1555C1H3R9CA01D": ("Murata", "GRM1555C1H3R9CA01D", "C85940"),
    "GRM1555C1H8R2CA01D": ("Murata", "GRM1555C1H8R2CA01D", "C76984"),
    "GRM1555C1H5R6CA01D": ("Murata", "GRM1555C1H5R6CA01D", "C85941"),
    "GRM1555C1H1R0BA01D": ("YAGEO", "CC0402BRNPO9BN1R0", "C309455"),        # +/-0.1 pF (balun)
    "GRM1555C1H1R5BA01D": ("FH", "0402CG1R5B500NT", "C285112"),             # +/-0.1 pF (balun)
    "GRM1555C1H3R3BA01D": ("YAGEO", "CC0402BRNPO9BN3R3", "C327287"),        # +/-0.1 pF (balun)
    "GRM1555C1H101JA01D": ("FH", "0402CG101J500NT", "C1546"),               # basic
    "GRM1555C1H120JA01D": ("FH", "0402CG120J500NT", "C1547"),               # basic
    "GRM1885C1H1R1CA01D": ("Murata", "GQM1875C2E1R1BB12D", "C3863168"),     # sub, high-Q
    "GRM1885C1H100JA01D": ("Samsung", "CL10C100JB8NNNC", "C1634"),          # basic
    "GRM1885C1H3R6CA01D": ("YAGEO", "CC0603BRNPO9BN3R6", "C519106"),        # sub
    "GRM1885C1H2R7CA01D": ("YAGEO", "CC0603CRNPO9BN2R7", "C282247"),        # sub
    "GRM1885C1H5R1CA01D": ("Murata", "GRM1885C1H5R1CA01D", "C6955114"),
    "GRM1885C1H6R2CA01D": ("YAGEO", "CC0603BRNPO9BN6R2", "C519113"),        # sub
    "GRM1885C1H510JA01D": ("YAGEO", "CC0603JRNPO9BN510", "C107051"),        # sub
    "LQG15HS27NJ02D": ("Murata", "LQG15HS27NJ02D", "C12669"),
    "LQG15HS22NJ02D": ("Murata", "LQG15HS22NJ02D", "C12670"),
    "LQW18AN39NG00D": ("Murata", "LQW18AN39NG00D", "C86134"),
    "LQW15AN12NJ00D": ("Murata", "LQW15AN12NJ00D", "C82920"),
    "LQW15AN18NJ00D": ("Murata", "LQW15AN18NJ00D", "C82917"),
    "TXS0108EPWR": ("Texas Instruments", "TXS0108EPWR", "C17206"),
}


def jlc(entry):
    d, mfr, mpn, lcsc = entry
    if mpn in JLC:
        mfr, mpn, lcsc = JLC[mpn]
    return d, mfr, mpn, lcsc


# Antenna match / tuning defaults (antenna/match.py) are chosen from these
# JLCPCB basic / preferred-extended 0603 parts (tune.py CHEAP_CAPS).
CHEAP_0603 = {
    "3pF": ("Capacitor 3 pF +/-0.25 pF C0G 50 V 0603 (antenna match)", "FH", "0603CG3R0C500NT", "C46219"),
    "4.7pF": ("Capacitor 4.7 pF +/-0.25 pF C0G 50 V 0603 (antenna match)", "FH", "0603CG4R7C500NT", "C1669"),
    "6pF": ("Capacitor 6 pF +/-0.25 pF C0G 50 V 0603 (antenna match)", "FH", "0603CG6R0C500NT", "C37474"),
    "6.8pF": ("Capacitor 6.8 pF +/-0.25 pF C0G 50 V 0603 (antenna match)", "FH", "0603CG6R8C500NT", "C1679"),
    "8.2pF": ("Capacitor 8.2 pF +/-0.25 pF C0G 50 V 0603 (antenna match)", "FH", "0603CG8R2C500NT", "C1685"),
    "10pF": ("Capacitor 10 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C100JB8NNNC", "C1634"),
    "12pF": ("Capacitor 12 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C120JB8NNNC", "C38523"),
    "15pF": ("Capacitor 15 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C150JB8NNNC", "C1644"),
    "18pF": ("Capacitor 18 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C180JB8NNNC", "C1647"),
    "20pF": ("Capacitor 20 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C200JB8NNNC", "C1648"),
    "22pF": ("Capacitor 22 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C220JB8NNNC", "C1653"),
    "27pF": ("Capacitor 27 pF 5% C0G 50 V 0603 (antenna match)", "YAGEO", "CC0603JRNPO9BN270", "C107045"),
    "30pF": ("Capacitor 30 pF 5% C0G 50 V 0603 (antenna match)", "FH", "0603CG300J500NT", "C1658"),
    "33pF": ("Capacitor 33 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C330JB8NNNC", "C1663"),
    "47pF": ("Capacitor 47 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C470JB8NNNC", "C1671"),
    "56pF": ("Capacitor 56 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C560JB8NNNC", "C39148"),
    "68pF": ("Capacitor 68 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C680JB8NNNC", "C28262"),
    "100pF": ("Capacitor 100 pF 5% C0G 50 V 0603 (antenna match)", "Samsung", "CL10C101JB8NNNC", "C14858"),
}


def fp_key(fpname):
    return next((k for k in FP_KEYS if k in fpname), None)


def lookup(fpname, value):
    return jlc(_lookup(fpname, value))


def _lookup(fpname, value):
    k = fp_key(fpname)
    if (k, value) in CAT:
        return CAT[(k, value)]
    if (k, None) in CAT:
        return CAT[(k, None)]
    if k in ("C_0603", "L_0603") and value in CHEAP_0603:
        return CHEAP_0603[value]
    m = re.match(r"([\d.]+)(pF|nH)$", value)
    if m and k in ("C_0603", "L_0603", "R_0603"):
        v, u = m.groups()
        x = float(v)
        if u == "pF":
            if x < 10:           # e.g. 3.6 pF -> 3R6, +/-0.25 pF (C)
                code, tol = f"{int(x)}R{round((x - int(x)) * 10):d}", "C"
            else:                # e.g. 16 pF -> 160, 5 % (J)
                e = 0
                while x >= 100:
                    x /= 10
                    e += 1
                code, tol = f"{int(round(x)):02d}{e}", "J"
            return (f"Capacitor {v} pF C0G 50 V 0603 (antenna match)", "Murata",
                    f"GRM1885C1H{code}{tol}A01D", "")
        return (f"Inductor {v} nH wire-wound 2 % 0603 (antenna tuning)", "Murata",
                f"LQW18AN{int(x)}NG00D", "")
    raise SystemExit(f"no catalog entry for {fpname} / {value}")


# Coil (helical spring) antennas for H1 (radio A) / H2 (radio B), hand-soldered
# like a Flipper-style internal coil; other bands: BW315SNX39-6W3 (C496553),
# BW915SNX17-5W2 (C496556).
COILS = [
    ("H1", "Coil antenna 433 MHz, spring 5 mm x 21 mm (radio A)", "BW433SNX21-5W2", "C496554"),
    ("H2", "Coil antenna 868 MHz, spring 5 mm x 20 mm (radio B)", "BW868SNX20-5Z6", "C496555"),
]


def hand_fit(name):
    """Optional parts left out of JLCPCB assembly to keep it cheap (no
    through-hole step, two fewer extended part types)."""
    return "PinHeader" in name or "SMA" in name


def bom_value(name, value):
    """J3/J4 carry their pin range as value; buy them as one line."""
    return "1x15 header" if "PinHeader" in name else value


def centre(fp):
    box = None
    for pad in fp.Pads():
        b = pad.GetBoundingBox()
        box = b if box is None else box.Merge(b) or box
    return box.GetCenter()


def main():
    board = pcbnew.LoadBoard(PCB)
    pcbnew.WriteDRCReport(board, os.path.join(HERE, "drc_report.txt"),
                          pcbnew.EDA_UNITS_MILLIMETRES, True)

    # ---- netlist ---------------------------------------------------------
    nets = collections.defaultdict(list)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() and pad.GetNumber():
                nets[pad.GetNetname()].append(f"{fp.GetReference()}.{pad.GetNumber()}")

    def key(p):
        r, n = p.split(".")
        m = re.match(r"([A-Z]+)(\d+)", r)
        return (m.group(1), int(m.group(2)), int(n) if n.isdigit() else 0)

    out = ["# Netlist", "",
           "Generated from the routed board by `pcb/fab_outputs.py` (KiCad DRC: 0 unconnected",
           "pads). `_A` nets belong to radio A (U1, 315/433 MHz), `_B` nets to radio B",
           "(U501, 868/915 MHz); SPI (SI/SO/SCLK) is shared.", "",
           "| Net | Pads |", "|---|---|"]
    for n in sorted(nets):
        out.append(f"| {n} | {', '.join(sorted(set(nets[n]), key=key))} |")
    open(os.path.join(HERE, "..", "netlist.md"), "w").write("\n".join(out) + "\n")

    # ---- BOM ---------------------------------------------------------------
    groups = collections.OrderedDict()
    fitted = []
    for fp in sorted(board.GetFootprints(), key=lambda f: key(f.GetReference() + ".0")):
        name = fp.GetFPIDAsString().split(":")[1]
        if any(s in name for s in NOT_PARTS):
            continue
        ref, value = fp.GetReference(), fp.GetValue()
        dnp = value.upper().startswith("DNP")
        cat = None if dnp else lookup(name, value)
        g = (name, value)
        groups.setdefault(g, {"refs": [], "cat": cat, "dnp": dnp})["refs"].append(ref)
        if not dnp:
            fitted.append((fp, name, value, cat))

    with open(os.path.join(HERE, "..", "bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["RefDes", "Qty", "Description", "Manufacturer", "MPN", "Package", "Notes"])
        for (name, value), g in groups.items():
            pkg = fp_key(name) or name
            if g["dnp"]:
                w.writerow([", ".join(g["refs"]), len(g["refs"]), f"not fitted ({value})",
                            "", "", pkg, "leave empty unless re-selecting the antenna"])
            else:
                d, mfr, mpn, lcsc = g["cat"]
                w.writerow([", ".join(g["refs"]), len(g["refs"]), d, mfr, mpn, pkg,
                            f"LCSC {lcsc}" if lcsc else ""])
        w.writerow(["S1, S2", 2, "Female header 1x15 2.54 mm (Nano socket)", "Generic", "",
                    "HDR-1x15-F", "optional; or solder the Nano directly"])
        for ref, d, mpn, lcsc in COILS:
            w.writerow([ref, 1, d, "BAT WIRELESS", mpn, "spring", f"optional, LCSC {lcsc}"])

    os.makedirs(os.path.join(HERE, "fab"), exist_ok=True)

    # Purchasing BOM: every fitted part except the Arduino Nano Every itself
    buy = collections.OrderedDict()
    for fp, name, value, (d, mfr, mpn, lcsc) in fitted:
        if "Arduino_Nano" in name:
            continue
        how = "hand solder (optional)" if hand_fit(name) else "SMT"
        buy.setdefault((d, mfr, mpn, lcsc, fp_key(name) or name, bom_value(name, value),
                        how), []).append(fp.GetReference())
    with open(os.path.join(HERE, "fab", "bom-no-nano.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Item", "Qty", "RefDes", "Value", "Description", "Manufacturer", "MPN",
                    "LCSC", "Package", "Fitting"])
        rows = sorted(buy.items(), key=lambda kv: (kv[0][6], key(kv[1][0] + ".0")))
        for i, ((d, mfr, mpn, lcsc, pkg, value, how), refs) in enumerate(rows, 1):
            w.writerow([i, len(refs), " ".join(refs), value, d, mfr, mpn, lcsc, pkg, how])
        w.writerow([len(rows) + 1, 2, "S1 S2", "1x15 F", "Female header 1x15 2.54 mm "
                    "(socket for the Nano Every)", "Generic", "", "", "HDR-1x15-F",
                    "hand solder"])
        for i, (ref, d, mpn, lcsc) in enumerate(COILS, len(rows) + 2):
            w.writerow([i, 1, ref, "coil", d, "BAT WIRELESS", mpn, lcsc, "spring, 1 pin",
                        "hand solder (optional; fit R403/R406 0R to use)"])

    jl = collections.OrderedDict()
    for fp, name, value, (d, mfr, mpn, lcsc) in fitted:
        if "Arduino_Nano" in name or hand_fit(name):
            continue        # the Nano plugs in; SMA jacks / J3,J4 are optional, by hand
        jl.setdefault((bom_value(name, value), name, mpn, lcsc), []).append(fp.GetReference())
    with open(os.path.join(HERE, "fab", "bom-jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN"])
        for (value, name, mpn, lcsc), refs in jl.items():
            w.writerow([value, ",".join(refs), name, lcsc, mpn])
    placed = {r for refs in jl.values() for r in refs}
    ox = pcbnew.ToMM(board.GetDesignSettings().GetAuxOrigin().x)
    oy = pcbnew.ToMM(board.GetDesignSettings().GetAuxOrigin().y)
    with open(os.path.join(HERE, "fab", "cpl-jlcpcb.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for fp in board.GetFootprints():
            if fp.GetReference() in placed:
                # part centre (the pad bounding box), not the footprint origin:
                # a pin header's origin is pin 1
                p = centre(fp) if "PinHeader" in fp.GetFPIDAsString() else fp.GetPosition()
                w.writerow([fp.GetReference(), f"{pcbnew.ToMM(p.x) - ox:.3f}mm",
                            f"{oy - pcbnew.ToMM(p.y):.3f}mm", "Top",
                            f"{fp.GetOrientationDegrees() % 360:.0f}"])
    print(f"BOM: {sum(len(g['refs']) for g in groups.values())} parts "
          f"({len(placed)} placed by the assembler), netlist: {len(nets)} nets")


if __name__ == "__main__":
    main()
