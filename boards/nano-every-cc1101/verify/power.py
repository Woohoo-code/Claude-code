"""Power and thermal budget (datasheet figures)."""
cc_tx = {"433 MHz +10 dBm": 29.2, "868 MHz +10 dBm": 30.0, "915 MHz +10 dBm": 30.7}   # CC1101 SWRS061I Table 5
cc_rx = 16.0                       # mA, RX sensitivity-optimised setting, typical
led = (3.3 - 2.0) / 1000 * 1e3     # red LED via R1 1k from 3V3
txs = 2.0                          # TXS0108E incl. switching at a few MHz SPI (generous)
worst = 2 * max(cc_tx.values()) + txs + led
print(f"3V3 load, both radios transmitting at +10 dBm: {worst:.0f} mA "
      f"(both receiving: {2 * cc_rx + txs + led:.0f} mA)")
print(f"XC6206P332MR: 200 mA rated -> {worst / 200 * 100:.0f} % used; dropout at 100 mA ~0.25 V, "
      f"headroom from the Nano's 5 V: {5.0 - 3.3:.1f} V")
p = (5.0 - 3.3) * worst / 1e3
print(f"LDO dissipation {p * 1e3:.0f} mW; SOT-23 theta_JA ~250 C/W -> +{p * 250:.0f} C rise "
      f"(Tj {25 + p * 250:.0f} C at 25 C ambient, limit 125 C)")
print(f"Nano Every 5 V pin: {worst + 5:.0f} mA of the 950 mA it can supply (datasheet power tree)")
print("CC1101 VDD 3.3 V +/-2 % (XC6206) within 1.8-3.6 V; TXS0108E VCCA 3.3 V <= VCCB 5 V as required")
