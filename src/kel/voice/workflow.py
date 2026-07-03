"""The explicit speech-to-text, conversation, and text-to-speech chain."""

from __future__ import annotations

from dataclasses import dataclass

from kel.conversation.session import ConversationSession
from kel.voice.contracts import AudioClip, SpeechGenerator, Transcriber, VoiceTurn


@dataclass(slots=True)
class VoiceWorkflow:
    """Run one recorded voice turn through visible, replaceable stages."""

    conversation: ConversationSession
    transcriber: Transcriber
    speech_generator: SpeechGenerator

    def respond(self, recording: AudioClip) -> VoiceTurn:
        """Transcribe the user, get Kel's text answer, then generate speech."""
        transcript = self.transcriber.transcribe(recording)
        reply = self.conversation.send(transcript)
        reply_audio = self.speech_generator.generate(reply.text)
        return VoiceTurn(
            transcript=transcript,
            reply_text=reply.text,
            reply_audio=reply_audio,
        )

    def reset(self) -> None:
        """Start a fresh underlying text conversation."""
        self.conversation.reset()
