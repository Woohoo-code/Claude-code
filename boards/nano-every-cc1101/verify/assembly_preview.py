"""Draw JLCPCB's own footprint of every CPL part (red) at its CPL position
and rotation over the rendered top Gerbers -- what JLCPCB's placement
preview will show. Misplaced / mis-rotated parts stand out immediately."""
import csv, sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import ez
from PIL import Image, ImageDraw
img_path, bom, cpl, out, H = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
im = Image.open(img_path).convert("RGB"); W_px, H_px = im.size; s = W_px / 70.0
d = ImageDraw.Draw(im)
lcsc = {}
for r in csv.DictReader(open(bom)):
    for x in r["Designator"].split(","): lcsc[x.strip()] = r["LCSC Part #"]
for r in csv.DictReader(open(cpl)):
    ref = r["Designator"]; X = float(r["Mid X"][:-2]); Y = float(r["Mid Y"][:-2]); th = math.radians(float(r["Rotation"]))
    e = ez.pads(lcsc[ref])
    for p in e["pads"]:
        if p["layer"] not in ("1", "11"): continue
        # EasyEDA pad (y-down) -> y-up, rotate CCW by th, place at (X, Y) y-up
        hw, hh = p["w"] / 2, p["h"] / 2
        corners = [(p["x"] + dx, -(p["y"] + dy)) for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
        pts = []
        for cx, cy in corners:
            rx, ry = cx * math.cos(th) - cy * math.sin(th), cx * math.sin(th) + cy * math.cos(th)
            pts.append(((X + rx) * s, (H - (Y + ry)) * s))
        d.polygon(pts, outline=(255, 30, 30), width=2)
    # pin-1 marker for polarised parts
    p1 = next((p for p in e["pads"] if p["num"] == "1"), None)
    if p1 and len(e["pads"]) > 2 and not ref.startswith(("J", "S")):
        cx, cy = p1["x"], -p1["y"]
        rx, ry = cx * math.cos(th) - cy * math.sin(th), cx * math.sin(th) + cy * math.cos(th)
        u, v = (X + rx) * s, (H - (Y + ry)) * s
        d.ellipse([u - 5, v - 5, u + 5, v + 5], fill=(0, 200, 255))
im.save(out); print("wrote", out)
