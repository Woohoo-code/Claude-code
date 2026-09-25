# Schematic, by block

No `.kicad_sch`: the circuit is described here and the exact connectivity
is in `netlist.md`, generated from the routed board.

## 1. Power

```
 Nano +5V (pin 27) ──┬── C5 1u ── GND
                     ├── U2 AP2112K-3.3  VIN, EN ── VOUT ──┬── 3V3 ── C6 10u ── GND
                     │                                     └── R1 1k ── D1 LED ── GND
                     └── U3 VCCB (+ C8 100n)
 3V3 ── U3 VCCA, OE (+ C7 100n), both CC1101s
```

## 2. Level shifter (U3 TXS0108E, A = 3.3 V radio side, B = 5 V Nano side)

| Ch | A (3.3 V) | B (5 V) | Nano pin |
|---|---|---|---|
| 1 | SCLK (both radios) | D13_SCK | D13 |
| 2 | SI (both) | D11_MOSI | D11 |
| 3 | SO (both, tri-stated by CSn) | D12_MISO | D12 |
| 4 | CSN_A | D10 | D10 |
| 5 | GDO0_A | D2 | D2 |
| 6 | GDO2_A | D3 | D3 |
| 7 | CSN_B | D9 | D9 |
| 8 | GDO0_B | D4 | D4 |

Radio B's GDO2 goes to test pad TP1 (3.3 V, not shifted).

## 3. CC1101 core (both radios; radio B refdes +500)

```
 3V3 ── DVDD(4), AVDD(9,11,14,15), DGUARD(18), each with 100 nF
        (C41, C111, C151, C181 / C541, C611, C651, C681)
 DCOUPL(5) ── C51 100n ── GND            (1.8 V core regulator only)
 RBIAS(17) ── R171 56k 1% ── GND
 XOSC_Q1(8) ── Y1 26 MHz ── XOSC_Q2(10), C81 / C101 27 pF to GND
 exposed pad + GND(16,19) ── GND (5 vias)
```

## 4. Radio A RF: 315/433 MHz balun + LC filter (SWRS061I Fig. 10)

```
 RF_N(13) ─┬─ L131 ───────┐
          C131            ├─ RF_J ── L122 ─┬─ L123 ─┬─ C125 ── ANT_A
          GND             │               C122     C123
 RF_P(12) ─┬─ C121 ───────┘                GND      GND
          L121 ── C124 ── GND
```
Fitted (433 MHz): C121/C131 3.9 pF, L121/L123/L131 27 nH, L122 22 nH,
C122 8.2 pF, C123 5.6 pF, C124/C125 220 pF.
315 MHz: C121/C131 6.8 pF, C122 12 pF, C123 6.8 pF, L121/L123/L131 33 nH, L122 18 nH.

## 5. Radio B RF: 868/915 MHz balun + filter (SWRS061I Fig. 11)

```
 RF_N(13) ── L131 12n ─┬─ N1 ─┬─ L132 18n ───┐
                    C121 1.0p C131 1.5p      ├─ RF_J ── L123 12n ─┬─ L124 12n ── C125 12p ── ANT_B
 RF_P(12) ── L121 12n ─┴─ P1 ─┼─ C122 1.5p ──┘                   C123 3.3p
                              L122 18n ── C124 100p ── GND        GND
```
(Refdes on the board: L631, L621, C621, C631, L632, C622, L622, C624, L623, C623, L624, C625.)

## 6. Antenna selection, T-matches and tuning parts

```
                 ┌─ R301 ─┬─ L301 ── 433 IFA ─[L401]─ arm   (short R401 to GND)
                 │        C301
 ANT_A ──────────┼─ R311 ─┬─ L311 ── 315 IFA ─[L402]─ arm   (short R402)
                 │        C311
                 └─ R403 ── EXT_A ── H1 (wire) ── J1 (SMA)

                 ┌─ R321 ─┬─ L321 ── 868 IFA ─[L404]─ arm   (short R404)
                 │        C321
 ANT_B ──────────┼─ R331 ─┬─ L331 ── 915 IFA ─[L405]─ arm   (short R405)
                 │        C331
                 └─ R406 ── EXT_B ── H2 (wire) ── J2 (SMA)
```
R3x1 = selector (fit one per radio), C3x1 = shunt, L3x1 = series, L40x =
series tuning part in the antenna arm. Any of these positions can hold a
capacitor, an inductor or 0 ohm. Values per frequency are in
`antenna/results/tuning.md`, and the defaults in `antenna/match.py`.

## 7. Nano Every + breakout

A1 = Nano Every on 2x 1x15 sockets. J3 duplicates pins 1-15 and J4 pins
16-30, each pad to pad.
