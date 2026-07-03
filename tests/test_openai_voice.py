from types import SimpleNamespace

from kel.voice.contracts import AudioClip
from kel.voice.openai_speech import OpenAISpeechGenerator
from kel.voice.openai_transcriber import OpenAITranscriber


class FakeTranscriptions:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        return SimpleNamespace(text="  Hello Kel  ")


class FakeSpeech:
    def __init__(self) -> None:
        self.request: dict[str, object] | None = None

    def create(self, **request: object) -> SimpleNamespace:
        self.request = request
        return SimpleNamespace(content=b"wav bytes")


def test_openai_transcriber_uploads_the_audio_clip() -> None:
    transcriptions = FakeTranscriptions()
    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions))
    transcriber = OpenAITranscriber(client=client, model="transcription-model")
    clip = AudioClip(data=b"audio", filename="recording.wav")

    transcript = transcriber.transcribe(clip)

    assert transcript == "Hello Kel"
    assert transcriptions.request == {
        "model": "transcription-model",
        "file": ("recording.wav", b"audio", "audio/wav"),
    }


def test_openai_speech_generator_requests_wav_audio() -> None:
    speech = FakeSpeech()
    client = SimpleNamespace(audio=SimpleNamespace(speech=speech))
    generator = OpenAISpeechGenerator(client=client, model="speech-model", voice="marin")

    result = generator.generate("Hello, builder!")

    assert result.data == b"wav bytes"
    assert result.filename == "kel-response.wav"
    assert speech.request == {
        "model": "speech-model",
        "voice": "marin",
        "input": "Hello, builder!",
        "instructions": "Speak warmly, naturally, and clearly as the robot Kel.",
        "response_format": "wav",
    }
