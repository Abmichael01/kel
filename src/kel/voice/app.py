"""Construct the concrete components used by Kel's voice interface."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from kel.ai.openai_chat import OpenAIChat
from kel.config.settings import Settings
from kel.conversation.session import ConversationSession
from kel.prompts.kel_personality import build_kel_instructions
from kel.voice.contracts import AudioPlayer, AudioRecorder
from kel.voice.microphone import SoundDeviceMicrophone
from kel.voice.openai_speech import OpenAISpeechGenerator
from kel.voice.openai_transcriber import OpenAITranscriber
from kel.voice.speaker import SoundDeviceSpeaker
from kel.voice.workflow import VoiceWorkflow


@dataclass(frozen=True, slots=True)
class VoiceApplication:
    """The components needed by a voice-facing user interface."""

    workflow: VoiceWorkflow
    recorder: AudioRecorder
    player: AudioPlayer


def build_voice_application(settings: Settings) -> VoiceApplication:
    """Create the chained voice workflow and local audio devices."""
    client = OpenAI(api_key=settings.openai_api_key)
    chat = OpenAIChat(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        instructions=build_kel_instructions(settings.robot_name),
        client=client,
    )
    conversation = ConversationSession(gateway=chat)
    workflow = VoiceWorkflow(
        conversation=conversation,
        transcriber=OpenAITranscriber(client=client, model=settings.transcription_model),
        speech_generator=OpenAISpeechGenerator(
            client=client,
            model=settings.speech_model,
            voice=settings.speech_voice,
        ),
    )
    recorder = SoundDeviceMicrophone(
        sample_rate=settings.microphone_sample_rate,
        device=settings.audio_input_device,
    )
    player = SoundDeviceSpeaker(device=settings.audio_output_device)
    return VoiceApplication(workflow=workflow, recorder=recorder, player=player)
