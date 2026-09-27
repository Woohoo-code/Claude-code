"""2-D electrostatic field solver for the board's grounded coplanar waveguide.
Solves Laplace's equation on the real cross-section (1.6 mm FR4 er=4.5, 35 um
copper, bottom ground plane, top ground pour at gap s) for C with and without
the dielectric; Z0 = 1/(c*sqrt(C*C_air)), eps_eff = C/C_air."""
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spl, sys
E0, C0 = 8.854e-12, 2.998e8
def solve(w, s, h=1.6, t=0.035, er=4.5, dx=0.01, half=4.0, air=3.0):
    nx = int(round(2 * half / dx)) + 1
    ny = int(round((h + t + air) / dx)) + 1
    x = np.linspace(-half, half, nx); y = np.arange(ny) * dx
    X, Y = np.meshgrid(x, y, indexing="ij")
    eps = np.where(Y < h, er, 1.0)                       # cell permittivity (node-based)
    cu = (Y >= h) & (Y <= h + t + 1e-9)
    strip = cu & (np.abs(X) <= w / 2)
    gnd = (cu & (np.abs(X) >= w / 2 + s)) | (Y <= 1e-12)
    fixed = strip | gnd
    fixed[0, :] = fixed[-1, :] = True; fixed[:, -1] = True   # far boundary = 0 V
    V0 = np.where(strip, 1.0, 0.0)
    def cap(epsmap):
        idx = -np.ones((nx, ny), int); free = ~fixed
        idx[free] = np.arange(free.sum())
        rows, cols, vals = [], [], []; b = np.zeros(free.sum())
        for (di, dj) in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ii, jj = np.nonzero(free)
            ni, nj = ii + di, jj + dj
            ok = (ni >= 0) & (ni < nx) & (nj >= 0) & (nj < ny)
            ii, jj, ni, nj = ii[ok], jj[ok], ni[ok], nj[ok]
            e = 0.5 * (epsmap[ii, jj] + epsmap[ni, nj])            # face permittivity
            rows += list(idx[ii, jj]); cols += list(idx[ii, jj]); vals += list(-e)
            nb_free = idx[ni, nj] >= 0
            rows += list(idx[ii, jj][nb_free]); cols += list(idx[ni, nj][nb_free]); vals += list(e[nb_free])
            np.add.at(b, idx[ii, jj][~nb_free], -e[~nb_free] * V0[ni, nj][~nb_free])
        A = sp.csr_matrix((vals, (rows, cols)), shape=(free.sum(),) * 2)
        V = V0.copy(); V[free] = spl.spsolve(A.tocsc(), b)
        # energy: W = 1/2 sum eps |grad V|^2  -> C = 2W (per unit length, V=1)
        ex = np.diff(V, axis=0); ey = np.diff(V, axis=1)
        eface_x = 0.5 * (epsmap[1:, :] + epsmap[:-1, :]); eface_y = 0.5 * (epsmap[:, 1:] + epsmap[:, :-1])
        return E0 * (np.sum(eface_x * ex**2) + np.sum(eface_y * ey**2))   # dx cancels in 2-D
    C = cap(eps); Ca = cap(np.ones_like(eps))
    return 1 / (C0 * np.sqrt(C * Ca)), C / Ca
if __name__ == "__main__":
    for w in [float(v) for v in sys.argv[1:]] or [0.25, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]:
        z, e = solve(w, 0.2)
        print(f"w={w:4.2f} mm gap 0.20 mm:  Z0 = {z:5.1f} ohm   eps_eff = {e:4.2f}", flush=True)
