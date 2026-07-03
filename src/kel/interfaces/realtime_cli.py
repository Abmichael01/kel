"""Terminal status display for Kel's continuous Realtime voice mode."""

from __future__ import annotations

import asyncio

from kel.config.settings import ConfigurationError, Settings
from kel.realtime.app import build_realtime_session
from kel.realtime.events import RealtimeDisplayEvent


class RealtimeTerminalDisplay:
    """Render provider-independent live conversation events."""

    def __init__(self, *, robot_name: str) -> None:
        self._robot_name = robot_name

    def show(self, event: RealtimeDisplayEvent) -> None:
        """Print one event without leaking transport details into the UI."""
        if event.kind == "connected":
            print(event.text)
        elif event.kind == "speech_started":
            print("\n[Listening]")
        elif event.kind == "speech_stopped":
            print("[Thinking]")
        elif event.kind == "user_transcript" and event.text:
            print(f"You: {event.text}")
        elif event.kind == "assistant_transcript" and event.text:
            print(f"{self._robot_name}: {event.text}")
        elif event.kind in (
            "interrupted",
            "looked",
            "remembered",
            "recalled",
            "acted",
            "type_mode",
        ):
            print(f"[{event.text}]")
        elif event.kind == "error":
            print(f"Realtime error: {event.text}")


async def run_realtime(settings: Settings) -> None:
    """Build and run one continuous voice session."""
    if settings.wake_enabled:
        from kel.wake.app import run_realtime_with_gate

        await run_realtime_with_gate(settings)
        return

    display = RealtimeTerminalDisplay(robot_name=settings.robot_name)
    session = build_realtime_session(settings, on_event=display.show)

    print(f"{settings.robot_name} realtime voice mode")
    print(f"Disclosure: {settings.robot_name}'s voice is AI-generated, not human.")
    print("Use headphones to prevent speaker echo. Press Ctrl+C to stop.")
    await session.run()


def main() -> None:
    """Load configuration and start the asynchronous Realtime session."""
    try:
        settings = Settings.from_env()
        if settings.wake_enabled:
            from kel.wake.app import validate_wake_settings

            validate_wake_settings(settings)
    except ConfigurationError as error:
        print(f"Setup needed: {error}")
        raise SystemExit(2) from error

    try:
        asyncio.run(run_realtime(settings))
    except KeyboardInterrupt:
        print(f"\n{settings.robot_name}: Goodbye!")
