"""First brain<->body test: ping the Arduino, then blink its built-in light.

Flash arduino/kel_blink/kel_blink.ino onto the board first, then run:

    uv run kel-blink                 # auto-detect the port
    uv run kel-blink /dev/ttyUSB0    # or name the port
"""

from __future__ import annotations

import glob
import sys
import time

from kel.body.serial_link import SerialLink


def _find_port() -> str | None:
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else _find_port()
    if not port:
        print("No Arduino found. Plug it in, or name the port: kel-blink /dev/ttyUSB0")
        raise SystemExit(1)

    print(f"Connecting to {port} ...")
    link = SerialLink.open(port)
    time.sleep(2)  # opening the port resets the Arduino; wait for it to boot
    try:
        print("ping ->", link.send("ping"))
        for _ in range(3):
            print("on   ->", link.send("on"))
            time.sleep(0.5)
            print("off  ->", link.send("off"))
            time.sleep(0.5)
        print("Done. If the little light blinked, the brain<->body pipe works!")
    finally:
        link.close()
