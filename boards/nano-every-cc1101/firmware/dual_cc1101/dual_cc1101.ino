// Dual CC1101 example for the nano-every-cc1101 board (Arduino Nano Every).
//
// Radio A (U1, 315/433 MHz front end, coil AE1 433 MHz): CSn D10, GDO0 D2, GDO2 D3
// Radio B (U501, 868/915 MHz front end, coil AE3 868 MHz): CSn D9, GDO0 D4
// Shared SPI: D13 SCK, D11 MOSI, D12 MISO (through the TXS0108E).
//
// Both radios listen all the time; received packets are printed with RSSI.
// Serial commands (115200 baud, newline-terminated):
//   a <text>     send <text> on radio A
//   b <text>     send <text> on radio B
//   fa <MHz>     retune radio A (387-464, or 300-348 with the 315 MHz BOM)
//   fb <MHz>     retune radio B (779-928)
//
// Needs the RadioLib library (Library Manager: "RadioLib").

#include <RadioLib.h>

CC1101 radioA = new Module(10, 2, RADIOLIB_NC, 3);
CC1101 radioB = new Module(9, 4, RADIOLIB_NC);

volatile bool rxA = false, rxB = false;
void onA() { rxA = true; }
void onB() { rxB = true; }

void check(const __FlashStringHelper *what, int16_t state) {
  if (state != RADIOLIB_ERR_NONE) {
    Serial.print(what);
    Serial.print(F(" failed, code "));
    Serial.println(state);
  }
}

void startRadio(CC1101 &r, const __FlashStringHelper *name, float mhz, void (*isr)()) {
  // 4.8 kbps GFSK, 5 kHz deviation, 58 kHz RX bandwidth, +10 dBm
  check(name, r.begin(mhz, 4.8, 5.0, 58.0, 10, 16));
  r.setPacketReceivedAction(isr);
  check(name, r.startReceive());
}

void printPacket(CC1101 &r, char tag) {
  String s;
  int16_t state = r.readData(s);
  if (state == RADIOLIB_ERR_NONE) {
    Serial.print(tag);
    Serial.print(F(" rx ["));
    Serial.print(r.getRSSI());
    Serial.print(F(" dBm] "));
    Serial.println(s);
  } else if (state == RADIOLIB_ERR_CRC_MISMATCH) {
    Serial.print(tag);
    Serial.println(F(" rx CRC error"));
  }
  r.startReceive();
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}
  // keep both chip selects high before either radio is touched
  pinMode(10, OUTPUT); digitalWrite(10, HIGH);
  pinMode(9, OUTPUT);  digitalWrite(9, HIGH);
  startRadio(radioA, F("radio A"), 433.92, onA);
  startRadio(radioB, F("radio B"), 868.3, onB);
  Serial.println(F("ready: a/b <text> to send, fa/fb <MHz> to retune"));
}

void loop() {
  if (rxA) { rxA = false; printPacket(radioA, 'A'); }
  if (rxB) { rxB = false; printPacket(radioB, 'B'); }

  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() < 2) return;
    bool isA = line[0] == 'a' || (line[0] == 'f' && line[1] == 'a');
    CC1101 &r = isA ? radioA : radioB;
    if (line[0] == 'f') {
      float mhz = line.substring(2).toFloat();
      check(F("setFrequency"), r.setFrequency(mhz));
      r.startReceive();
      Serial.print(isA ? F("A at ") : F("B at "));
      Serial.println(mhz, 3);
    } else {
      String msg = line.substring(2);
      check(F("transmit"), r.transmit(msg));
      Serial.print(isA ? F("A tx ") : F("B tx "));
      Serial.println(msg);
      r.startReceive();
    }
  }
}
