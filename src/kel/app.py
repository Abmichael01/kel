"""Application composition: create and connect Kel's independent modules."""

from kel.ai.openai_chat import OpenAIChat
from kel.config.settings import Settings
from kel.conversation.session import ConversationSession
from kel.prompts.kel_personality import build_kel_instructions


def build_conversation(settings: Settings) -> ConversationSession:
    """Build a conversation session from explicit application settings."""
    gateway = OpenAIChat(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        instructions=build_kel_instructions(settings.robot_name),
    )
    return ConversationSession(gateway=gateway)
