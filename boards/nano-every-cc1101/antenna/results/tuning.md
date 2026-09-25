# Antenna tuning for every CC1101 frequency

Pick your frequency, fit the four parts on that row (all 0603), fit the
antenna's selector, and the antenna is resonant and matched there. The
full per-MHz tables are `tuning_<band>.csv`. The **power to antenna** figure
is the share of the radio's output left after the tuning and match parts'
losses (radiation efficiency of the antenna itself not included).

## 433 MHz antenna: 387-464 MHz

| MHz | tune L401 | S1 R301 | shunt C301 | S2 L301 | S11 | power to antenna |
|---|---|---|---|---|---|---|
| 390 | 10nH | 0R | 27pF | 13pF | -27.1 dB | 77 % |
| 395 | 5.6nH | 0R | 39pF | 13pF | -24.8 dB | 83 % |
| 400 | 1.5nH | 0R | 47pF | 13pF | -26.8 dB | 88 % |
| 405 | 0R | 0R | 36pF | 13pF | -20.7 dB | 92 % |
| 410 | 0R | 0R | 27pF | 12pF | -26.2 dB | 94 % |
| 415 | 0R | 0R | 18pF | 11pF | -23.6 dB | 96 % |
| 420 | 0R | 0R | 11pF | 9.1pF | -29.6 dB | 97 % |
| 425 | 100pF | 0R | 11pF | 9.1pF | -27.9 dB | 98 % |
| 430 | 100pF | 0R | 2pF | 5.6pF | -39.4 dB | 99 % |
| 433.92 | 51pF | 0R | 1.1pF | 5.1pF | -64.0 dB | 99 % |
| 435 | 43pF | 0R | 2.2pF | 5.6pF | -43.7 dB | 99 % |
| 440 | 91pF | 0R | 47nH | 0R | -29.5 dB | 98 % |
| 445 | 43pF | 0R | 39nH | 0R | -32.1 dB | 98 % |
| 450 | 27pF | 0R | 47nH | 1.8nH | -29.7 dB | 97 % |
| 455 | 20pF | 0R | 39nH | 1.5nH | -28.7 dB | 97 % |
| 460 | 56pF | 0R | 27pF | 0R | -38.7 dB | 96 % |

## 315 MHz antenna: 300-348 MHz

| MHz | tune L402 | S1 R311 | shunt C311 | S2 L311 | S11 | power to antenna |
|---|---|---|---|---|---|---|
| 300 | 56nH | 0R | 20pF | 22pF | -31.8 dB | 45 % |
| 305 | 56nH | 0R | 5.1pF | 43pF | -47.3 dB | 43 % |
| 310 | 47nH | 0R | 27pF | 18pF | -26.0 dB | 42 % |
| 315 | 39nH | 2.7pF | 10pF | 0R | -34.4 dB | 41 % |
| 320 | 39nH | 0R | 33pF | 16pF | -28.4 dB | 43 % |
| 325 | 27nH | 0R | 75pF | 16pF | -21.9 dB | 47 % |
| 330 | 18nH | 0R | 91pF | 16pF | -17.4 dB | 51 % |
| 335 | 22nH | 0R | 62pF | 15pF | -18.3 dB | 55 % |
| 340 | 10nH | 0R | 91pF | 15pF | -20.5 dB | 60 % |
| 345 | 18nH | 1.8pF | 9.1pF | 0R | -21.9 dB | 61 % |

## 868 MHz antenna: 779-880 MHz

| MHz | tune L404 | S1 R321 | shunt C321 | S2 L321 | S11 | power to antenna |
|---|---|---|---|---|---|---|
| 780 | 0R | 0R | 9.1pF | 3.3pF | -26.1 dB | 97 % |
| 785 | 0R | 0R | 7.5pF | 3.3pF | -24.3 dB | 97 % |
| 790 | 0R | 1.2pF | 1.1pF | 0R | -27.3 dB | 97 % |
| 795 | 0R | 1.3pF | 1pF | 0R | -28.3 dB | 98 % |
| 800 | 0R | 0R | 5.6pF | 3pF | -28.1 dB | 98 % |
| 805 | 0R | 0R | 4.7pF | 3pF | -35.3 dB | 98 % |
| 810 | 0R | 0R | 3.9pF | 3pF | -41.8 dB | 99 % |
| 815 | 0R | 0R | 3.3pF | 3pF | -41.5 dB | 99 % |
| 820 | 0R | 0R | 2.7pF | 3pF | -34.8 dB | 99 % |
| 825 | 0R | 0R | 2.4pF | 3pF | -33.9 dB | 99 % |
| 830 | 0R | 0R | 2pF | 3pF | -31.3 dB | 99 % |
| 835 | 0R | 0R | 2pF | 3.3pF | -33.4 dB | 99 % |
| 840 | 0R | 0R | 1.6pF | 3.3pF | -33.9 dB | 99 % |
| 845 | 0R | 0R | 1.3pF | 3.3pF | -34.1 dB | 99 % |
| 850 | 0R | 0R | 1.5pF | 3.9pF | -33.6 dB | 99 % |
| 855 | 0R | 0R | 2pF | 4.7pF | -39.1 dB | 99 % |
| 860 | 0R | 0R | 2.4pF | 5.6pF | -34.4 dB | 99 % |
| 865 | 0R | 0R | 3pF | 6.2pF | -33.1 dB | 99 % |
| 868.3 | 0R | 0R | 3.6pF | 6.2pF | -41.7 dB | 99 % |
| 870 | 0R | 0R | 3.9pF | 6.2pF | -34.1 dB | 99 % |
| 875 | 0R | 0R | 4.3pF | 5.6pF | -31.8 dB | 99 % |
| 880 | 0R | 0R | 5.1pF | 4.7pF | -28.3 dB | 99 % |

## 915 MHz antenna: 870-928 MHz

| MHz | tune L405 | S1 R331 | shunt C331 | S2 L331 | S11 | power to antenna |
|---|---|---|---|---|---|---|
| 870 | 0R | 0R | 5.6pF | 4.3pF | -36.7 dB | 99 % |
| 875 | 0R | 0R | 6.2pF | 3.9pF | -27.5 dB | 98 % |
| 880 | 0R | 1.3pF | 1.2pF | 0R | -35.5 dB | 98 % |
| 885 | 0R | 0R | 6.8pF | 3.3pF | -23.9 dB | 98 % |
| 890 | 0R | 0R | 6.2pF | 3.3pF | -21.6 dB | 98 % |
| 895 | 0R | 0R | 5.6pF | 3pF | -26.0 dB | 98 % |
| 900 | 0R | 1.2pF | 0.82pF | 0R | -32.1 dB | 98 % |
| 905 | 0R | 0R | 4.3pF | 2.7pF | -34.9 dB | 98 % |
| 910 | 0R | 0R | 3.6pF | 2.7pF | -26.7 dB | 99 % |
| 915 | 0R | 0R | 2.7pF | 2.7pF | -25.8 dB | 99 % |
| 920 | 0R | 0R | 2.2pF | 2.7pF | -29.6 dB | 99 % |
| 925 | 0R | 0R | 2pF | 2.7pF | -40.5 dB | 99 % |

Radio A needs the 315 MHz front-end BOM for 300-348 MHz and the 433 MHz
BOM for 387-464 MHz; radio B's 868/915 front end covers 779-928 MHz.

## External whip (SMA J1/J2 or wire in H1/H2): any frequency

Fit R403 (radio A) or R406 (radio B) instead of a printed-antenna selector.
A quarter-wave whip over the board's ground plane is about
**L (mm) = 71 250 / f (MHz)** (0.95 x lambda/4). A telescopic SMA whip set
to this length, or a wire soldered into H1/H2 and cut to it, works at every
CC1101 frequency.

| MHz | whip (mm) | MHz | whip (mm) | MHz | whip (mm) |
|---|---|---|---|---|---|
| 300 | 238 | 387 | 184 | 779 | 91 |
| 305 | 234 | 390 | 183 | 780 | 91 |
| 310 | 230 | 395 | 180 | 790 | 90 |
| 315 | 226 | 400 | 178 | 800 | 89 |
| 320 | 223 | 405 | 176 | 810 | 88 |
| 325 | 219 | 410 | 174 | 820 | 87 |
| 330 | 216 | 415 | 172 | 830 | 86 |
| 335 | 213 | 420 | 170 | 840 | 85 |
| 340 | 210 | 425 | 168 | 850 | 84 |
| 345 | 207 | 430 | 166 | 860 | 83 |
| 348 | 205 | 433.92 | 164 | 868.3 | 82 |
|  |  | 435 | 164 | 870 | 82 |
|  |  | 440 | 162 | 880 | 81 |
|  |  | 445 | 160 | 890 | 80 |
|  |  | 450 | 158 | 900 | 79 |
|  |  | 455 | 157 | 910 | 78 |
|  |  | 460 | 155 | 915 | 78 |
|  |  | 464 | 154 | 920 | 77 |
|  |  |  |  | 928 | 77 |
