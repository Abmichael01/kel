from kel.ai.gateway import AIReply
from kel.conversation.session import ConversationSession
from kel.voice.contracts import AudioClip
from kel.voice.workflow import VoiceWorkflow


class FakeChatGateway:
    def reply(self, user_text: str, previous_response_id: str | None = None) -> AIReply:
        assert user_text == "Hello Kel"
        assert previous_response_id is None
        return AIReply(text="Hello, builder!", response_id="response-1")


class FakeTranscriber:
    def transcribe(self, audio: AudioClip) -> str:
        assert audio.filename == "microphone.wav"
        return "Hello Kel"


class FakeSpeechGenerator:
    def generate(self, text: str) -> AudioClip:
        assert text == "Hello, builder!"
        return AudioClip(data=b"generated audio", filename="reply.wav")


def test_voice_workflow_keeps_each_stage_visible() -> None:
    workflow = VoiceWorkflow(
        conversation=ConversationSession(gateway=FakeChatGateway()),
        transcriber=FakeTranscriber(),
        speech_generator=FakeSpeechGenerator(),
    )

    turn = workflow.respond(AudioClip(data=b"recorded audio", filename="microphone.wav"))

    assert turn.transcript == "Hello Kel"
    assert turn.reply_text == "Hello, builder!"
    assert turn.reply_audio.data == b"generated audio"
