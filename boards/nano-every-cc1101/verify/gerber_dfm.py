"""DFM check on the Gerber/drill output itself (what the fab receives):
smallest aperture actually drawn per layer vs JLCPCB 2-layer limits."""
import re, sys, glob, os, zipfile, io
LIMITS = {"silk": 0.15, "copper": 0.10, "drill_via": 0.15, "drill_pth": 0.15}
z = zipfile.ZipFile(sys.argv[1]); ok = True
for name in sorted(z.namelist()):
    txt = z.read(name).decode()
    if name.lower().endswith(".drl"):
        tools = {t: float(d) for t, d in re.findall(r"^(T\d+)C([\d.]+)", txt, re.M)}
        used = set(re.findall(r"^(T\d+)$", txt, re.M))
        sizes = sorted(tools[t] for t in used)
        print(f"{name:40} drills used: {', '.join(f'{s:.2f}' for s in sizes)} mm  (min {LIMITS['drill_via']})")
        ok &= sizes[0] >= LIMITS["drill_via"]; continue
    ap = {d: s for d, s in re.findall(r"%ADD(\d+)[A-Za-z]+,([\d.]+)", txt)}
    used = set(re.findall(r"(?:^|\*)D(\d{2,})\*", txt, re.M))
    kind = "silk" if name.lower().endswith((".gto", ".gbo")) else "copper" if name.lower().endswith((".gtl", ".gbl")) else None
    drawn = sorted(float(ap[d]) for d in used if d in ap)
    msg = f"min aperture {drawn[0]:.3f} mm" if drawn else "no apertures"
    if kind:
        lim = LIMITS[kind]; good = not drawn or drawn[0] >= lim - 1e-6
        ok &= good; msg += f"  (limit {lim}) {'OK' if good else 'TOO THIN'}"
    print(f"{name:40} {msg}")
print("GERBER DFM: " + ("PASS" if ok else "FAIL"))
