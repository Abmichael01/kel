"""Hand-test the body once it's wired up:

    uv run kel-body ping
    uv run kel-body color 255 0 0      # red
    uv run kel-body color 0 80 255     # calm blue
    uv run kel-body servo 9 90         # servo on pin 9 to 90 degrees
"""

from __future__ import annotations

import sys
import time

from kel.body.controller import BodyController
from kel.body.serial_link import SerialLink, find_port

_USAGE = "usage: kel-body ping | color R G B | servo PIN ANGLE"


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(_USAGE)
        raise SystemExit(1)

    port = find_port()
    if not port:
        print("No Arduino found. Plug it in.")
        raise SystemExit(1)

    link = SerialLink.open(port)
    time.sleep(2)  # opening the port resets the Arduino; wait for it to boot
    body = BodyController(link)
    try:
        command = args[0]
        if command == "ping":
            print("ping ->", body.ping())
        elif command == "color" and len(args) >= 4:
            print("color ->", body.set_color(int(args[1]), int(args[2]), int(args[3])))
        elif command == "servo" and len(args) >= 3:
            print("servo ->", body.move_servo(int(args[1]), int(args[2])))
        else:
            print(_USAGE)
    finally:
        link.close()
