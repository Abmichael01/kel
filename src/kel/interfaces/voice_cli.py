"""Push-to-talk terminal interface for Kel's first voice milestone."""

from __future__ import annotations

from collections.abc import Callable

from kel.config.settings import ConfigurationError, Settings
from kel.voice.app import VoiceApplication, build_voice_application

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


def run_voice_chat(
    application: VoiceApplication,
    *,
    robot_name: str,
    read: InputFunction = input,
    write: OutputFunction = print,
) -> None:
    """Run a visible push-to-talk loop around the chained voice workflow."""
    write(f"{robot_name} voice mode is ready.")
    write(f"Disclosure: {robot_name}'s voice is AI-generated, not a human voice.")
    write("Use headphones if the speaker sound feeds back into the microphone.")

    while True:
        try:
            command = read("\nPress Enter to talk, or type /help: ").strip().casefold()
        except (EOFError, KeyboardInterrupt):
            write(f"\n{robot_name}: Goodbye!")
            return

        if command in {"/exit", "/quit"}:
            write(f"{robot_name}: Goodbye!")
            return
        if command == "/reset":
            application.workflow.reset()
            write("Conversation reset.")
            continue
        if command == "/help":
            write("Press Enter to record. Commands: /reset and /exit.")
            continue
        if command:
            write("Voice mode expects Enter or a command. Use `uv run kel` for typed chat.")
            continue

        try:
            application.recorder.start()
            read("Recording... speak now, then press Enter to stop. ")
            recording = application.recorder.stop()
        except (EOFError, KeyboardInterrupt):
            application.recorder.cancel()
            write(f"\n{robot_name}: Goodbye!")
            return
        except Exception as error:
            application.recorder.cancel()
            write(f"Microphone error: {error}")
            continue

        write("Transcribing, thinking, and preparing speech...")
        try:
            turn = application.workflow.respond(recording)
        except Exception as error:
            write(f"{robot_name} could not answer: {error}")
            continue

        write(f"You said: {turn.transcript}")
        write(f"{robot_name}: {turn.reply_text}")
        try:
            application.player.play(turn.reply_audio)
        except Exception as error:
            write(f"Speaker error: {error}")


def main() -> None:
    """Load settings, assemble the voice application, and start its terminal UI."""
    try:
        settings = Settings.from_env()
    except ConfigurationError as error:
        print(f"Setup needed: {error}")
        raise SystemExit(2) from error

    application = build_voice_application(settings)
    run_voice_chat(application, robot_name=settings.robot_name)
