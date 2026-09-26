"""Fetch + parse EasyEDA (JLCPCB/LCSC) footprints: pads in mm, y-down, rel. to origin."""
import json, os, subprocess, time
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "easyeda_cache")
def fetch(code):
    f = os.path.join(CACHE, code + ".json")
    if not os.path.exists(f):
        for a in range(4):
            subprocess.run(["curl", "-sS", "-m", "30", "-o", f,
                            f"https://easyeda.com/api/products/{code}/components?version=6.4.19.5"])
            try:
                json.load(open(f))["result"]["packageDetail"]; break
            except Exception:
                time.sleep(2 * (a + 1))
    return json.load(open(f))["result"]
def pads(code):
    r = fetch(code)
    d = r["packageDetail"]["dataStr"]; h = d["head"]
    ox, oy = float(h["x"]), float(h["y"])
    out = []; body = []
    for s in d["shape"]:
        f = s.split("~")
        if f[0] == "PAD":
            out.append(dict(num=f[8], x=(float(f[2]) - ox) * 0.254, y=(float(f[3]) - oy) * 0.254,
                            w=float(f[4]) * 0.254, h=float(f[5]) * 0.254, layer=f[6],
                            hole=float(f[9]) * 0.254 * 2 if f[9] else 0.0))
        elif f[0] == "SOLIDREGION" and f[1] in ("99", "12"):     # courtyard / component outline
            import re
            nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", f[3])]
            body += [((nums[i] - ox) * 0.254, (nums[i + 1] - oy) * 0.254) for i in range(0, len(nums) - 1, 2)]
    # symbol pin names by PAD number (the pin's second text is its pad number)
    names = {}
    for s in r["dataStr"]["shape"]:
        if s.startswith("P~"):
            texts = [g.split("~")[4] for g in s.split("^^")[1:] if len(g.split("~")) > 4 and g.split("~")[0] in ("0", "1")]
            if len(texts) >= 2 and texts[1]:
                names[texts[1]] = texts[0]
    return dict(title=r["title"], package=r["packageDetail"]["title"], pads=out, body=body, names=names)
