// Kel body — first test sketch.
// The Arduino is "dumb muscle": it listens for one-word commands over USB and
// blinks the built-in LED. The Python brain (kel-blink) sends the commands.
//
// Flash this with the Arduino IDE (Tools -> Board = your Arduino, pick the Port),
// then on the computer run:  uv run kel-blink

const int LED = LED_BUILTIN;  // the little light already on the board (pin 13)

void setup() {
  Serial.begin(9600);         // must match baud=9600 on the Python side
  pinMode(LED, OUTPUT);
}

void loop() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "ping") {
      Serial.println("pong");
    } else if (cmd == "on") {
      digitalWrite(LED, HIGH);
      Serial.println("led on");
    } else if (cmd == "off") {
      digitalWrite(LED, LOW);
      Serial.println("led off");
    } else {
      Serial.println("?");
    }
  }
}
