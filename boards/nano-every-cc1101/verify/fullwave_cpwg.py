"""3-D full-wave (openEMS FDTD) check of the 50 ohm line, independent of the
2-D electrostatic solver: a 50 mm run of the board's grounded coplanar
waveguide (1.2 mm strip, 0.2 mm gaps, 1.6 mm FR4 er 4.5, bottom ground) in
the same shielded cross-section as fieldsolve.py (grounds to +/-4 mm, lid
3 mm above), zero-thickness copper, driven and terminated by openEMS
microstrip ports (strip-to-ground voltage, current around the strip).
The line impedance comes from the travelling wave at the port (Z_ref)."""
import os, sys, tempfile, numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
W, S, H, AIR, HALF, L = 1.2, 0.2, 1.6, 3.0, 4.0, 50.0
f = np.linspace(0.3e9, 1.0e9, 29)
path = os.environ.get("CPWG_PATH") or tempfile.mkdtemp(prefix="cpwg_")
RUN = not os.environ.get("CPWG_PATH")          # CPWG_PATH=<dir>: re-read an earlier run
FDTD = openEMS(NrTS=300000, EndCriteria=1e-5)
FDTD.SetGaussExcite(1.0e9, 1.0e9)
FDTD.SetBoundaryCond(["PML_8", "PML_8", "PEC", "PEC", "PEC", "PEC"])   # shield like the 2-D model
CSX = ContinuousStructure(); FDTD.SetCSX(CSX)
mesh = CSX.GetGrid(); mesh.SetDeltaUnit(1e-3)
# mesh: uniform 0.05 mm across the strip and gaps (every copper edge on a line,
# no tiny cells that would shrink the time step), graded outside
y = list(np.arange(-1.0, 1.0001, 0.05)) + list(np.arange(1.2, HALF + 1e-6, 0.2)) + list(-np.arange(1.2, HALF + 1e-6, 0.2))
mesh.AddLine("y", sorted(set(np.round(y, 4))))
mesh.AddLine("x", np.arange(0, L + 1e-6, 0.4))
z = list(np.linspace(-H, 0, 17)) + [-0.05, 0.05, 0.12, 0.2, 0.3, 0.45, 0.65, 0.9, 1.3, 1.8, 2.4, AIR]
mesh.AddLine("z", sorted(set(np.round(z, 4))))
fr4 = CSX.AddMaterial("FR4", epsilon=4.5)
fr4.AddBox([0, -HALF, -H], [L, HALF, 0], priority=0)
pec = CSX.AddMetal("PEC")
for sgn in (1, -1):                                          # coplanar ground pours
    pec.AddBox([0, sgn * (W / 2 + S), 0], [L, sgn * HALF, 0], priority=10)
pec.AddBox([0, -W / 2, 0], [L, W / 2, 0], priority=10)       # the strip
# feed and measurement planes well clear of the 8-cell (3.2 mm) absorbing layers
p1 = FDTD.AddMSLPort(1, pec, [0, -W / 2, 0], [14, W / 2, -H], "x", "z", excite=1, FeedShift=5.2, MeasPlaneShift=10, priority=20)
p2 = FDTD.AddMSLPort(2, pec, [L, -W / 2, 0], [L - 14, W / 2, -H], "x", "z", MeasPlaneShift=10, priority=20)
if RUN:
    FDTD.Run(path, verbose=0, cleanup=True, numThreads=int(os.environ.get("THREADS", "4")))
p1.CalcPort(path, f)                              # travelling-wave line impedance
Z = np.real(p1.Z_ref).copy()
for p in (p1, p2):
    p.CalcPort(path, f, ref_impedance=50)          # S-parameters against 50 ohm
s11 = 20 * np.log10(np.abs(p1.uf_ref / p1.uf_inc)); s21 = 20 * np.log10(np.abs(p2.uf_ref / p1.uf_inc))
# eps_eff from the S21 phase over the 30 mm between the two measurement planes
ph = np.unwrap(np.angle(p2.uf_ref / p1.uf_inc)); d = (L - 2 * 10) * 1e-3
eps_eff = (-ph / d / (2 * np.pi * f / 2.998e8)) ** 2
print(f"3-D FDTD (openEMS), zero-thickness copper, 0.3-1.0 GHz:")
print(f"  Z0 = {Z.mean():.1f} ohm (range {Z.min():.1f}-{Z.max():.1f})   eps_eff = {eps_eff.mean():.2f}")
print(f"  S11 into 50 ohm: worst {s11.max():.1f} dB   S21: {s21.min():.2f} to {s21.max():.2f} dB")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fieldsolve import solve
z2, e2 = solve(W, S, t=0.0)
z2t, e2t = solve(W, S)
print(f"2-D field solver, same cross-section: Z0 = {z2:.1f} ohm, eps_eff = {e2:.2f} (zero-thickness copper); "
      f"{z2t:.1f} ohm with the real 35 um copper")
print(f"FULL-WAVE vs 2-D: {abs(Z.mean() - z2):.1f} ohm apart -> " + ("AGREE" if abs(Z.mean() - z2) < 2.0 else "DISAGREE"))
