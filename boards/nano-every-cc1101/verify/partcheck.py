"""Each assembly BOM line vs the live JLCPCB/LCSC record: package, value, description,
library class, stock. Prints a table for review and flags value/package mismatches."""
import csv, json, subprocess, sys, time, re
def q(code):
    for a in range(5):
        out = subprocess.run(["curl", "-sS", "-m", "30", "-X", "POST",
            "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList",
            "-H", "Content-Type: application/json", "-d", json.dumps({"keyword": code, "currentPage": 1, "pageSize": 10})],
            capture_output=True, text=True).stdout
        try:
            return next(c for c in json.loads(out)["data"]["componentPageInfo"]["list"] if c["componentCode"] == code)
        except Exception:
            time.sleep(3 * (a + 1))
rows = list(csv.DictReader(open(sys.argv[1]))); cache = {}; bad = []
UNIT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "k": 1e3, "M": 1e6, "": 1.0, "m": 1e-3}
def num(t):
    m = re.match(r"([\d.]+)\s*([pnumkM]?)", t.replace("μ", "u").replace("Ω", "").replace("R", ""))
    return float(m.group(1)) * UNIT[m.group(2)] if m else None
def verdict(r, c, attrs):
    """value and package of the BOM line against the LCSC record"""
    fp, com, desc = r["Footprint"], r["Comment"], c["describe"]
    size = next((z for z in ("0402", "0603", "0805") if f"_{z}_" in fp), None)
    if size and size not in (c["componentSpecificationEn"] or ""):
        return f"package {c['componentSpecificationEn']} != {size}"
    for key, attr in (("C_", "Capacitance"), ("L_", "Inductance"), ("R_", "Resistance")):
        if fp.startswith(key) and com not in ("0R",):
            want, got = num(com), num(attrs.get(attr, ""))
            if want is None or got is None or abs(want - got) > 1e-6 * want: return f"{attr} {attrs.get(attr)} != {com}"
            return "OK"
    if com == "0R":
        return "OK" if attrs.get("Resistance", "").startswith("0") else f"not 0 ohm: {attrs.get('Resistance')}"
    if fp.startswith("Crystal"):
        return "OK" if "26MHz" in desc and "16pF" in desc else "crystal mismatch"
    if fp.startswith("LED"):
        return "OK" if "Red" in desc and size in desc else "LED mismatch"
    m, w = (x.replace("-", "").replace(" ", "").upper() for x in (c["componentModelEn"], r["MPN"]))
    return "OK" if m == w or m.startswith(w) or w.startswith(m) else f"MPN {c['componentModelEn']} != {r['MPN']}"
for r in rows:
    c = q(r["LCSC Part #"]); cache[r["LCSC Part #"]] = c
    attrs = {a["attribute_name_en"]: a["attribute_value_name"] for a in (c.get("attributes") or [])}
    print(f"{r['LCSC Part #']:9} | BOM: {r['Comment']:16} {r['Footprint'][:34]:34} | LCSC: {c['componentModelEn'][:22]:22} pkg={c['componentSpecificationEn']:12} "
          f"lib={c['componentLibraryType']:6} pref={c.get('preferredComponentFlag')} stock={c['stockCount']}")
    print(f"          describe: {c['describe'][:150]}")
    v_ = verdict(r, c, attrs)
    if v_ != "OK": bad.append(f"{r['LCSC Part #']} {r['Comment']}: {v_}")
    print(f"          check: {v_}")
    keep = {k: v for k, v in attrs.items() if any(s in k for s in ("Capacitance", "Inductance", "Resistance", "Tolerance", "Voltage", "Temperature Coefficient", "Frequency", "Load Capacitance", "Q @", "Self Resonant", "Current", "Pitch", "Number of Pins", "Pins", "Mounting", "Color", "Output Voltage", "Dropout", "Impedance"))}
    if keep: print(f"          attrs: {keep}")
    time.sleep(0.3)
json.dump(cache, open(sys.argv[2], "w"))
print("PARTS vs LCSC: " + ("ALL %d LINES MATCH (value, package, MPN)" % len(rows) if not bad else "MISMATCH\n  " + "\n  ".join(bad)))
sys.exit(1 if bad else 0)
