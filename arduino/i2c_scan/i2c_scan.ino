// Temporary diagnostic: scan the I2C bus and report what's connected.
#include <Wire.h>

void setup() {
  Serial.begin(9600);
  Wire.begin();
  delay(400);
  Serial.println("I2C-SCAN-START");
  int n = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print("FOUND 0x");
      Serial.println(a, HEX);
      n++;
    }
  }
  Serial.print("I2C-SCAN-DONE count=");
  Serial.println(n);
}

void loop() {}
