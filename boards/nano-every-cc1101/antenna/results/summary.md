# Antenna results (openEMS)

| Antenna | Arm (mm) | Tap / tail (mm) | Z at f0 (ohm) | S11 unmatched | T-match S1 / shunt / S2 | S11 matched | -10 dB band (MHz) | match loss |
|---|---|---|---|---|---|---|---|---|
| 433 MHz | 153 | 3 / 52 | 73.8-13.9j | -13.1 dB | 16pF / 56nH / 0R | -15.9 dB | 431-437 | 0.1 dB |
| 315 MHz | 211 | 4 / 50 | 27.7+55.2j | -4.1 dB | 0R / 27nH / 6.8pF | -18.7 dB | 313-317 | 0.1 dB |
| 868 MHz | 60 | 4 / 10 | 26.6+53.8j | -4.1 dB | 0R / 3.6pF / 6.2pF | -31.0 dB | 847-883 | 0.0 dB |
| 915 MHz | 58 | 4 / 8 | 36.4+90.1j | -2.7 dB | 0R / 2.4pF / 2.7pF | -26.1 dB | 899-1041 | 0.0 dB |

Match loss = power lost in the T-match parts (0603, inductor Q 40, capacitor Q 300).
315 MHz additionally loses power in its arm's 47 nH loading coil (L402, Q 40): coil + match pass about 40 % (-4 dB) of the power on to the antenna (`choose_load.py`), so expect noticeably less range at 315 MHz than on the other bands.
ISM bands covered by the -10 dB bands: 433.05-434.79 (433), 314-316 (315), 863-870 (868), 902-928 (915).
