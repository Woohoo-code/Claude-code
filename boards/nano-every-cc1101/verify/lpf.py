"""CC1101 front-end low-pass sections (TI SWRS061I Fig.10/11 values) as built,
50 ohm to 50 ohm, with part parasitics: 0402 caps ESL 0.35 nH, Q 300;
inductors with their datasheet-typical Q and self-resonance."""
import numpy as np
def abcd_series(z): return np.array([[1, z], [0, 1]], complex)
def abcd_shunt(y): return np.array([[1, 0], [y, 1]], complex)
def Zl(L, f, q=30, srf=4e9):
    w = 2*np.pi*f; Cp = 1/((2*np.pi*srf)**2*L)
    zl = w*L/q + 1j*w*L
    return 1/(1/zl + 1j*w*Cp)
def Zc(C, f, esl=0.35e-9, q=300):
    w = 2*np.pi*f; x = -1/(w*C)
    return abs(x)/q + 1j*(x + w*esl)
def s21(chain, f, z0=50):
    M = np.eye(2, dtype=complex)
    for kind, fn in chain:
        z = fn(f); M = M @ (abcd_series(z) if kind == "s" else abcd_shunt(1/z))
    A, B, C, D = M.ravel()
    return 20*np.log10(abs(2/(A + B/z0 + C*z0 + D)))
# 433: J -> L122 22n -> (C122 8.2p) -> L123 27n -> (C123 5.6p) -> C125 330p -> ANT
lpf433 = [("s", lambda f: Zl(22e-9, f, 20, 3.4e9)), ("p", lambda f: Zc(8.2e-12, f)),
          ("s", lambda f: Zl(27e-9, f, 20, 3.0e9)), ("p", lambda f: Zc(5.6e-12, f)),
          ("s", lambda f: Zc(330e-12, f))]
# 868/915: J -> L123 12n -> (C123 3.3p) -> L124 12n -> C125 12p -> ANT
lpf868 = [("s", lambda f: Zl(12e-9, f, 35, 5.0e9)), ("p", lambda f: Zc(3.3e-12, f)),
          ("s", lambda f: Zl(12e-9, f, 35, 5.0e9)), ("s", lambda f: Zc(12e-12, f))]
for name, ch, f0s in (("433 MHz front end", lpf433, (433.92e6,)), ("868/915 front end", lpf868, (868.3e6, 915e6))):
    for f0 in f0s:
        print(f"{name} @ {f0/1e6:6.1f} MHz: pass {s21(ch, f0):5.2f} dB | "
              f"2nd {s21(ch, 2*f0):6.1f} dB | 3rd {s21(ch, 3*f0):6.1f} dB | 4th {s21(ch, 4*f0):6.1f} dB")
