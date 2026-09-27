"""Firmware -> board trace: every pin the sketch uses, through the Nano Every
header, the TXS0108E channel it lands on, to the CC1101 pin it must reach."""
import json, re, sys
FP = json.load(open(sys.argv[1])); ino = open(sys.argv[2]).read()
net_of = {(r, p[0]): p[5] for r, v in FP.items() for p in v["pads"]}
pads_on = {}
for (r, n), net in net_of.items():
    pads_on.setdefault(net, set()).add((r, n))
# Nano Every header pin (A1 pad) for Arduino pin Dn: pads 5..16 = D2..D13 (ABX00028)
nano_pad = {f"D{d}": str(d + 3) for d in range(2, 14)}
# TXS0108E: B side (5 V) pin -> A side (3.3 V) pin, channels 1..8
TXS = {"20": "1", "18": "3", "17": "4", "16": "5", "15": "6", "14": "7", "13": "8", "12": "9"}
CC = {"SCLK": "1", "SO": "2", "GDO2": "3", "GDO0": "6", "CSn": "7", "SI": "20"}
def through(dpin):
    net5 = net_of[("A1", nano_pad[dpin])]
    b = [n for r, n in pads_on[net5] if r == "U3"]
    if len(b) != 1: return None, net5, None
    net33 = net_of[("U3", TXS[b[0]])]
    return net33, net5, b[0]
ok = True
mods = re.findall(r"CC1101\s+(\w+)\s*=\s*new\s+Module\(([^)]*)\)", ino)
radios = {"radioA": "U1", "radioB": "U501"}
for name, args in mods:
    a = [x.strip() for x in args.split(",")]
    roles = [("CSn", a[0]), ("GDO0", a[1])] + ([("GDO2", a[3])] if len(a) > 3 and a[3] != "RADIOLIB_NC" else [])
    for role, pin in roles:
        net33, net5, bpin = through(f"D{pin}")
        want = net_of[(radios[name], CC[role])]
        good = net33 == want; ok &= good
        print(f"{name:7} {role:5} D{pin:<3} -> Nano pad {nano_pad[f'D{pin}']:>2} ({net5}) -> TXS B{bpin}/A -> {net33} "
              f"== {radios[name]}.{CC[role]} {role} ({want}): {'OK' if good else 'WRONG'}")
for role, d in (("SCLK", "D13"), ("SI", "D11"), ("SO", "D12")):      # hardware SPI of the Nano Every
    net33, net5, bpin = through(d)
    for u in ("U1", "U501"):
        want = net_of[(u, CC[role])]; good = net33 == want; ok &= good
        print(f"SPI     {role:5} {d:4} -> {net5} -> TXS -> {net33} == {u}.{CC[role]} ({want}): {'OK' if good else 'WRONG'}")
print("FIRMWARE PIN MAP: " + ("MATCHES THE BOARD" if ok else "MISMATCH"))
sys.exit(0 if ok else 1)
