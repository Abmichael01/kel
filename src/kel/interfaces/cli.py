"""Terminal interface for Kel's first conversational milestone."""

from __future__ import annotations

from collections.abc import Callable

from kel.app import build_conversation
from kel.config.settings import ConfigurationError, Settings
from kel.conversation.session import ConversationSession

InputFunction = Callable[[str], str]
OutputFunction = Callable[[str], None]


def run_chat(
    session: ConversationSession,
    *,
    robot_name: str,
    read: InputFunction = input,
    write: OutputFunction = print,
) -> None:
    """Run the interactive terminal loop around an existing conversation session."""
    write(f"{robot_name} is ready. Type /help for commands.")

    while True:
        try:
            user_text = read("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            write(f"\n{robot_name}: Goodbye!")
            return

        if not user_text:
            continue

        command = user_text.casefold()
        if command in {"/exit", "/quit"}:
            write(f"{robot_name}: Goodbye!")
            return
        if command == "/reset":
            session.reset()
            write("Conversation reset. The next message starts a fresh chat.")
            continue
        if command == "/help":
            write("Commands: /reset starts over, /exit closes Kel.")
            continue

        try:
            reply = session.send(user_text)
        except Exception as error:  # The CLI is the boundary that presents provider failures.
            write(f"{robot_name} could not answer: {error}")
            continue

        write(f"{robot_name}: {reply.text}")


def main() -> None:
    """Load configuration, assemble the application, and start the terminal UI."""
    try:
        settings = Settings.from_env()
    except ConfigurationError as error:
        print(f"Setup needed: {error}")
        raise SystemExit(2) from error

    session = build_conversation(settings)
    run_chat(session, robot_name=settings.robot_name)
