"""Check every IC / polarized part's pins against the vendor's pin names
(JLCPCB/EasyEDA symbols) and the Nano Every against the ABX00028 datasheet."""
import json, sys, re, math
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import ez
FP = json.load(open(sys.argv[1])); ok = True
def nets(ref): return {p[0]: p[5] for p in FP[ref]["pads"]}
def check(ref, code, rule):
    global ok
    names = ez.pads(code)["names"]; n = nets(ref); bad = []
    for pad, name in sorted(names.items(), key=lambda t: int(t[0]) if t[0].isdigit() else 99):
        exp = rule(name, n); got = n.get(pad, "")
        good = bool(re.fullmatch(exp, got)) if exp else True
        if not good: bad.append(f"pad {pad} {name}: net {got!r}, expected {exp}")
    print(f"{ref:5} {code:8} {len(names):2} pins vs vendor names: " + ("OK" if not bad else "FAIL\n   " + "\n   ".join(bad)))
    ok &= not bad
cc = lambda s: {"SCLK": "SCLK", "SO(GDO1)": "SO", "GDO2": "GDO2_"+s, "DVDD": "3V3", "AVDD": "3V3",
                "DGUARD": "3V3", "DCOUPL": "DCOUPL_"+s, "GDO0(ATEST)": "GDO0_"+s, "CSn": "CSN_"+s,
                "XOSC_Q1": "XOSC_Q1_"+s, "XOSC_Q2": "XOSC_Q2_"+s, "RF_P": "RF_P_"+s, "RF_N": "RF_N_"+s,
                "GND": "GND", "EP": "GND", "RBIAS": "RBIAS_"+s, "SI": "SI"}
check("U1", "C29953", lambda nm, n: cc("A").get(nm))
check("U501", "C29953", lambda nm, n: cc("B").get(nm))
check("U2", "C5446", lambda nm, n: {"GND": "GND", "Vin": r"\+5V", "Vout": "3V3"}.get(nm))
check("Y1", "C70573", lambda nm, n: {"OSC1": "XOSC_Q1_A", "OSC2": "XOSC_Q2_A", "GND": "GND"}.get(nm))
check("Y501", "C70573", lambda nm, n: {"OSC1": "XOSC_Q1_B", "OSC2": "XOSC_Q2_B", "GND": "GND"}.get(nm))
n = nets("D1"); led_ok = n.get("1") == "GND" and n.get("2") == "LED_A"
print("D1    C2286    LED: KiCad pad 1 (cathode) = GND, pad 2 (anode) = LED_A: " + ("OK" if led_ok else f"FAIL {n}"))
ok &= led_ok
# TXS0108E: supplies + each channel's A/B pair must be the same signal
pairs = {"SCLK": "D13_SCK", "SI": "D11_MOSI", "SO": "D12_MISO", "CSN_A": "D10", "GDO0_A": "D2",
         "GDO2_A": "D3", "CSN_B": "D9", "GDO0_B": "D4"}
names = ez.pads("C17206")["names"]; n = nets("U3"); byname = {v: n[k] for k, v in names.items()}
bad = [f"{s}: {byname.get(s)}" for s, e in (("VCCA", "3V3"), ("VCCB", "+5V"), ("OE", "3V3"), ("GND", "GND")) if byname.get(s) != e]
for k in range(1, 9):
    a, b = byname.get(f"A{k}"), byname.get(f"B{k}")
    if pairs.get(a) != b: bad.append(f"channel {k}: A{k}={a} B{k}={b}")
print(f"U3    C17206   TXS0108E supplies/OE + 8 channel pairs: " + ("OK  (" + ", ".join(f"A{k}={byname[f'A{k}']}" for k in range(1, 9)) + ")" if not bad else "FAIL " + str(bad)))
ok &= not bad
# Nano Every (ABX00028 datasheet table 6.2) vs A1 pad nets
DS = ["D13", "+3V3", "AREF", "A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "+5V", "RST", "GND", "VIN",
      "TX", "RX", "RST", "GND", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12"]
want = {"D13": "D13_SCK", "+3V3": "3V3_NANO", "AREF": "AREF", "A4": "A4_SDA", "A5": "A5_SCL", "+5V": r"\+5V",
        "TX": "D1_TX", "RX": "D0_RX", "D11": "D11_MOSI", "D12": "D12_MISO"}
n = nets("A1"); bad = []
for kp in range(1, 31):
    ds = kp + 15 if kp <= 15 else kp - 15
    name = DS[ds - 1]; exp = want.get(name, re.escape(name))
    if not re.fullmatch(exp, n[str(kp)]): bad.append(f"KiCad pad {kp} = datasheet pin {ds} {name}: net {n[str(kp)]}")
print("A1    Nano Every 30 pins vs ABX00028 datasheet: " + ("OK" if not bad else "FAIL " + str(bad)))
ok &= not bad
# decoupling distance: each IC supply pad -> nearest capacitor pad on the same net (other pad on GND)
caps = {r: v for r, v in FP.items() if r.startswith("C") and sorted(p[5] for p in v["pads"])[0] == "GND" or
        (r.startswith("C") and any(p[5] == "GND" for p in v["pads"]))}
print("decoupling (supply pin -> nearest cap on that net):")
for ref, pins in (("U1", ("4", "9", "11", "14", "15", "18")), ("U501", ("4", "9", "11", "14", "15", "18")),
                  ("U3", ("2", "19")), ("U2", ("2", "3"))):
    for pin in pins:
        p = next(q for q in FP[ref]["pads"] if q[0] == pin)
        best = min(((math.dist(p[1:3], q[1:3]), r) for r, v in caps.items() for q in v["pads"]
                    if q[5] == p[5] and any(z[5] == "GND" for z in v["pads"])), default=(99, "-"))
        print(f"   {ref}.{pin:>2} ({p[5]:5}) -> {best[1]:5} {best[0]:4.1f} mm")
print("ALL PIN CHECKS PASS" if ok else "PIN CHECK FAILURES")
