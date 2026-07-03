"""Run Kel's face in a desktop window and let her brain drive it over a socket.

    uv run kel-face --demo      # cycle moods so you can see the face
    uv run kel-face             # wait for the brain to drive it on 127.0.0.1:8765

The socket speaks the same line protocol as the Arduino body, plus a talking signal:
    mode <name>   ->  ok      speak <0|1>  ->  ok
    look <x> <y>  ->  ok      ping         ->  pong
"""

from __future__ import annotations

import argparse
import queue
import socket
import threading
from typing import Any

import pygame

from kel.face.screen import FaceRenderer

DEMO_MOODS = [
    "sleeping", "listening", "thinking", "happy", "excited", "playful", "love",
    "surprised", "confused", "angry", "sad", "calm", "alert", "normal",
]
_KEY_MOODS = [
    "listening", "happy", "excited", "playful", "love",
    "sad", "angry", "surprised", "confused", "sleeping",
]


def _apply(line: str, commands: queue.Queue[tuple[str, Any]]) -> str:
    """Parse one protocol line, queue it for the render loop, and reply."""
    parts = line.split()
    if not parts:
        return "?"
    cmd = parts[0].lower()
    if cmd == "ping":
        return "pong"
    if cmd == "mode" and len(parts) >= 2:
        commands.put(("mode", parts[1].lower()))
        return "ok"
    if cmd == "speak" and len(parts) >= 2:
        commands.put(("speak", parts[1].lower() not in ("0", "off", "false", "no")))
        return "ok"
    if cmd == "look" and len(parts) >= 3:
        try:
            commands.put(("look", (float(parts[1]), float(parts[2]))))
        except ValueError:
            return "err"
        return "ok"
    return "?"


def _handle(conn: socket.socket, commands: queue.Queue[tuple[str, Any]]) -> None:
    with conn, conn.makefile("rwb") as stream:
        for raw in stream:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                stream.write((_apply(line, commands) + "\n").encode())
                stream.flush()
            except OSError:
                break


def _serve(host: str, port: int, commands: queue.Queue[tuple[str, Any]]) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    while True:
        conn, _ = server.accept()
        threading.Thread(target=_handle, args=(conn, commands), daemon=True).start()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kel's animated face window.")
    parser.add_argument("--demo", action="store_true", help="cycle moods automatically")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fullscreen", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    pygame.init()
    pygame.display.set_caption("Kel")
    flags = pygame.FULLSCREEN if args.fullscreen else pygame.RESIZABLE
    # For real fullscreen, (0, 0) tells SDL to use the monitor's own resolution; passing a
    # fixed window size requests that exact video mode, which often fails or letterboxes -
    # the reason the face wasn't filling the screen. The face renders to whatever size it
    # gets, so the native resolution just works.
    size = (0, 0) if args.fullscreen else (args.width, args.height)
    screen = pygame.display.set_mode(size, flags)
    width, height = screen.get_size()
    clock = pygame.time.Clock()
    face = FaceRenderer(width=width, height=height)

    commands: queue.Queue[tuple[str, Any]] = queue.Queue()
    threading.Thread(target=_serve, args=(args.host, args.port, commands), daemon=True).start()
    print(f"Kel's face is up. Driving socket: {args.host}:{args.port}")
    print("Keys: Esc quit · Space talk · F fullscreen · 1-0 mood · +/- eye size")

    demo_index = 0
    demo_timer = 0.0
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE and not args.fullscreen:
                screen = pygame.display.set_mode((event.w, event.h), flags)
            elif event.type == pygame.KEYDOWN:
                running = _on_key(event, face)

        while not commands.empty():
            action, value = commands.get()
            if action == "mode":
                face.set_mood(value)
            elif action == "speak":
                face.set_speaking(value)
            elif action == "look":
                face.look(*value)

        if args.demo:
            demo_timer += dt
            if demo_timer >= 2.6:
                demo_timer = 0.0
                face.set_mood(DEMO_MOODS[demo_index % len(DEMO_MOODS)])
                face.set_speaking(demo_index % 3 == 1)
                demo_index += 1

        face.update(dt)
        face.draw(screen)
        pygame.display.flip()

    pygame.quit()


def _on_key(event: pygame.event.Event, face: FaceRenderer) -> bool:
    """Handle a keypress; return False to quit."""
    if event.key == pygame.K_ESCAPE:
        return False
    if event.key == pygame.K_SPACE:
        face.set_speaking(not face.speaking)
    elif event.key == pygame.K_f:
        pygame.display.toggle_fullscreen()
    elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
        print(f"eye scale: {face.nudge_scale(0.06):.2f}")
    elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
        print(f"eye scale: {face.nudge_scale(-0.06):.2f}")
    elif pygame.K_1 <= event.key <= pygame.K_9:
        face.set_mood(_KEY_MOODS[event.key - pygame.K_1])
    elif event.key == pygame.K_0:
        face.set_mood(_KEY_MOODS[9])
    return True


if __name__ == "__main__":
    main()
