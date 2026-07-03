import io
import wave

from kel.voice.microphone import encode_pcm_as_wav


def test_pcm_encoder_creates_a_readable_mono_wav() -> None:
    wav_data = encode_pcm_as_wav(b"\x00\x00" * 160, sample_rate=16_000)

    with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16_000
        assert wav_file.getnframes() == 160
