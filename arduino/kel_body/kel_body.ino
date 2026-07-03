// Kel body — living-orb RGB + servo + an animated FACE (eyes + mouth) on a 16x2
// I2C LCD. The LED rolls each mood's colour fast; the LCD shows two eyes that blink
// on their own plus a mouth, both changing with the mood. One `mode <name>` drives
// everything. The brain doesn't need to know the screen exists.
//
//   ping / mode <name> / rgb <r> <g> <b> / servo <pin> <deg>
//
// WIRING (Uno): RGB common-cathode R->5 G->6 B->3 (each via ~220ohm, common->GND).
//   Servos: signal -> 9/10/11 (own 5V supply, grounds tied).
//   I2C LCD: GND->GND, VCC->5V, SDA->A4, SCL->A5.

#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const int R_PIN = 5, G_PIN = 6, B_PIN = 3;
const int SERVO_PINS[] = {9, 10, 11};
const int SERVO_COUNT = 3;
Servo servos[SERVO_COUNT];

LiquidCrystal_I2C *lcd = nullptr;

enum { E_OPEN, E_CLOSED, E_HAPPY, E_SAD, E_WIDE, E_SLEEPY, E_UP, E_LOVE };
enum { M_FLAT, M_SMILE, M_FROWN, M_OPEN };

struct Mood {
  const char *name;
  uint8_t hMin, hMax, spd, sat, val;
  bool breathe;
  uint8_t eye, mouth;
};

const Mood MOODS[] = {
  {"sleeping",   0,   0, 0, 255, 255, true,  E_SLEEPY, M_FLAT},
  {"listening", 80, 120, 3, 255, 255, false, E_OPEN,   M_FLAT},
  {"thinking", 120, 170, 4, 255, 255, false, E_UP,     M_FLAT},
  {"typing",   190, 230, 4, 255, 255, false, E_OPEN,   M_FLAT},
  {"happy",     64, 115, 5, 255, 255, false, E_HAPPY,  M_SMILE},
  {"excited",    0,  64, 7, 255, 255, false, E_WIDE,   M_OPEN},
  {"sad",      150, 175, 2, 255, 150, false, E_SAD,    M_FROWN},
  {"playful",    0, 255, 6, 255, 255, false, E_HAPPY,  M_SMILE},
  {"love",     220, 255, 4, 255, 255, false, E_LOVE,   M_SMILE},
  {"calm",     120, 160, 2, 255, 210, false, E_SLEEPY, M_FLAT},
  {"alert",      0,  18, 9, 255, 255, false, E_WIDE,   M_OPEN},
  {"normal",     0, 255, 1,  70, 180, false, E_OPEN,   M_FLAT},
};
const int MOOD_COUNT = sizeof(MOODS) / sizeof(MOODS[0]);

const uint8_t EYES[][8] = {
  {0x00, 0x0E, 0x11, 0x15, 0x15, 0x11, 0x0E, 0x00},  // E_OPEN
  {0x00, 0x00, 0x00, 0x1F, 0x1F, 0x00, 0x00, 0x00},  // E_CLOSED
  {0x00, 0x00, 0x0E, 0x11, 0x00, 0x00, 0x00, 0x00},  // E_HAPPY
  {0x00, 0x0E, 0x11, 0x11, 0x15, 0x15, 0x0E, 0x00},  // E_SAD
  {0x0E, 0x11, 0x15, 0x15, 0x15, 0x15, 0x11, 0x0E},  // E_WIDE
  {0x00, 0x00, 0x00, 0x0E, 0x15, 0x0E, 0x00, 0x00},  // E_SLEEPY
  {0x00, 0x0E, 0x15, 0x15, 0x11, 0x11, 0x0E, 0x00},  // E_UP
  {0x00, 0x0A, 0x1F, 0x1F, 0x0E, 0x04, 0x00, 0x00},  // E_LOVE (heart)
};

// Each mouth is 3 cells (left, middle, right) drawn on the bottom row.
const uint8_t MOUTHS[][3][8] = {
  { // M_FLAT  ___
    {0, 0, 0, 0, 0x1F, 0, 0, 0}, {0, 0, 0, 0, 0x1F, 0, 0, 0}, {0, 0, 0, 0, 0x1F, 0, 0, 0},
  },
  { // M_SMILE  \_/
    {0, 0, 0x08, 0x04, 0x02, 0x01, 0, 0}, {0, 0, 0, 0, 0, 0x1F, 0, 0}, {0, 0, 0x02, 0x04, 0x08, 0x10, 0, 0},
  },
  { // M_FROWN  /‾\
    {0, 0, 0x01, 0x02, 0x04, 0x08, 0, 0}, {0, 0, 0x1F, 0, 0, 0, 0, 0}, {0, 0, 0x10, 0x08, 0x04, 0x02, 0, 0},
  },
  { // M_OPEN  ( )
    {0, 0x03, 0x04, 0x08, 0x08, 0x04, 0x03, 0}, {0, 0x1F, 0, 0, 0, 0, 0x1F, 0}, {0, 0x18, 0x04, 0x02, 0x02, 0x04, 0x18, 0},
  },
};

uint8_t aHMin = 0, aHMax = 0, aSpd = 0, aSat = 255, aVal = 255;
uint8_t curEye = E_SLEEPY, curMouth = M_FLAT;
bool aBreathe = true, animating = true;
const char *curMood = "sleeping";
int hue = 0, hueDir = 1, breathV = 20, breathDir = 1;
int staticR = 0, staticG = 0, staticB = 0;
unsigned long lastTick = 0, nextBlink = 0, blinkEnd = 0;
bool blinking = false;

char line[48];
int lineLen = 0;

int clampByte(int v)  { return v < 0 ? 0 : (v > 255 ? 255 : v); }
int clampAngle(int v) { return v < 0 ? 0 : (v > 180 ? 180 : v); }

void hsv(uint8_t h, uint8_t s, uint8_t v, int &r, int &g, int &b) {
  uint8_t region = h / 43, rem = (h % 43) * 6;
  uint8_t p = (uint16_t)v * (255 - s) / 255;
  uint8_t q = (uint16_t)v * (255 - ((uint16_t)s * rem) / 255) / 255;
  uint8_t t = (uint16_t)v * (255 - ((uint16_t)s * (255 - rem)) / 255) / 255;
  switch (region) {
    case 0: r = v; g = t; b = p; break;
    case 1: r = q; g = v; b = p; break;
    case 2: r = p; g = v; b = t; break;
    case 3: r = p; g = q; b = v; break;
    case 4: r = t; g = p; b = v; break;
    default: r = v; g = p; b = q; break;
  }
}

void copyChar(uint8_t slot, const uint8_t *src) {
  uint8_t tmp[8];
  for (int i = 0; i < 8; i++) tmp[i] = src[i];
  lcd->createChar(slot, tmp);
}

void writeEyes(uint8_t eye) {
  if (!lcd) return;
  copyChar(0, EYES[eye]);
  lcd->setCursor(5, 0); lcd->write((uint8_t)0);
  lcd->setCursor(10, 0); lcd->write((uint8_t)0);
}

void drawFace() {
  if (!lcd) return;
  lcd->clear();
  writeEyes(curEye);
  copyChar(1, MOUTHS[curMouth][0]);
  copyChar(2, MOUTHS[curMouth][1]);
  copyChar(3, MOUTHS[curMouth][2]);
  // Mouth across cols 6-9 (left, mid, mid, right): centred under the eyes (5 & 10),
  // with equal 6-cell margins on each side.
  lcd->setCursor(6, 1);
  lcd->write((uint8_t)1); lcd->write((uint8_t)2); lcd->write((uint8_t)2); lcd->write((uint8_t)3);
  if (strcmp(curMood, "sleeping") == 0) { lcd->setCursor(14, 1); lcd->print("z"); }
}

void applyMood(const Mood &m) {
  aHMin = m.hMin; aHMax = m.hMax; aSpd = m.spd;
  aSat = m.sat; aVal = m.val; aBreathe = m.breathe;
  hue = m.hMin; hueDir = 1; animating = true;
  curMood = m.name; curEye = m.eye; curMouth = m.mouth;
  blinking = false;
  drawFace();
}

void processCommand(char *cmd) {
  int a, b, c;
  char name[24];
  if (strncmp(cmd, "ping", 4) == 0) {
    Serial.println("pong");
  } else if (sscanf(cmd, "mode %23s", name) == 1) {
    for (int i = 0; i < MOOD_COUNT; i++) {
      if (strcmp(MOODS[i].name, name) == 0) { applyMood(MOODS[i]); break; }
    }
    Serial.println("ok");
  } else if (sscanf(cmd, "rgb %d %d %d", &a, &b, &c) == 3) {
    animating = false;
    staticR = clampByte(a); staticG = clampByte(b); staticB = clampByte(c);
    Serial.println("ok");
  } else if (sscanf(cmd, "servo %d %d", &a, &b) == 2) {
    int idx = -1;
    for (int i = 0; i < SERVO_COUNT; i++) if (SERVO_PINS[i] == a) idx = i;
    if (idx >= 0) { servos[idx].write(clampAngle(b)); Serial.println("ok"); }
    else Serial.println("err: bad pin");
  } else {
    Serial.println("?");
  }
}

uint8_t findLcd() {
  for (uint8_t addr = 0; addr < 128; addr++) {
    if (addr == 0x27 || addr == 0x3F) {
      Wire.beginTransmission(addr);
      if (Wire.endTransmission() == 0) return addr;
    }
  }
  return 0;
}

void setup() {
  Serial.begin(9600);
  pinMode(R_PIN, OUTPUT);
  pinMode(G_PIN, OUTPUT);
  pinMode(B_PIN, OUTPUT);
  for (int i = 0; i < SERVO_COUNT; i++) servos[i].attach(SERVO_PINS[i]);

  Wire.begin();
  Wire.setWireTimeout(3000, true);  // never hang the body if the LCD is miswired
  uint8_t addr = findLcd();
  if (addr) {
    lcd = new LiquidCrystal_I2C(addr, 16, 2);
    lcd->init();
    lcd->backlight();
  }
  applyMood(MOODS[0]);
}

void loop() {
  while (Serial.available() > 0) {
    char ch = Serial.read();
    if (ch == '\n') { line[lineLen] = '\0'; processCommand(line); lineLen = 0; }
    else if (lineLen < (int)sizeof(line) - 1) line[lineLen++] = ch;
  }

  unsigned long now = millis();

  if (lcd && animating) {  // blink the eyes (mouth stays put)
    if (!blinking && now >= nextBlink) {
      blinking = true; blinkEnd = now + 150; writeEyes(E_CLOSED);
    } else if (blinking && now >= blinkEnd) {
      blinking = false; nextBlink = now + 3200; writeEyes(curEye);
    }
  }

  if (now - lastTick < 10) return;
  lastTick = now;

  int r = staticR, g = staticG, b = staticB;
  if (animating) {
    if (aBreathe) {
      breathV += breathDir * 3;
      if (breathV >= 160) { breathV = 160; breathDir = -1; }
      if (breathV <= 20)  { breathV = 20;  breathDir = 1; }
      hsv(aHMin, aSat, breathV, r, g, b);
    } else {
      hue += hueDir * aSpd;
      if (hue >= aHMax) { hue = aHMax; hueDir = -1; }
      if (hue <= aHMin) { hue = aHMin; hueDir = 1; }
      hsv((uint8_t)hue, aSat, aVal, r, g, b);
    }
  }
  analogWrite(R_PIN, r);
  analogWrite(G_PIN, g);
  analogWrite(B_PIN, b);
}
