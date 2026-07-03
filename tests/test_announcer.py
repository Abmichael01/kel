"""The announcer speaks short wake/sleep acknowledgements from cached audio."""

from __future__ import annotations

from kel.voice.contracts import AudioClip
from kel.wake.announcer import SpokenAnnouncer


class FakeSpeechGenerator:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def generate(self, text: str) -> AudioClip:
        self.texts.append(text)
        return AudioClip(data=f"audio:{text}".encode())


class FakePlayer:
    def __init__(self) -> None:
        self.played: list[AudioClip] = []

    def play(self, audio: AudioClip) -> None:
        self.played.append(audio)


def build_announcer(
    *, greeting: str = "Hi", farewell: str = "Bye"
) -> tuple[SpokenAnnouncer, FakeSpeechGenerator, FakePlayer]:
    generator = FakeSpeechGenerator()
    player = FakePlayer()
    announcer = SpokenAnnouncer(
        speech_generator=generator,
        player=player,
        greeting=greeting,
        farewell=farewell,
    )
    return announcer, generator, player


def test_greet_renders_and_plays_the_greeting() -> None:
    announcer, generator, player = build_announcer()

    announcer.greet()

    assert generator.texts == ["Hi"]
    assert [clip.data for clip in player.played] == [b"audio:Hi"]


def test_greet_reuses_the_cached_clip() -> None:
    announcer, generator, player = build_announcer()

    announcer.greet()
    announcer.greet()

    assert generator.texts == ["Hi"]  # rendered once, replayed twice
    assert len(player.played) == 2


def test_farewell_renders_and_plays_the_farewell() -> None:
    announcer, generator, player = build_announcer()

    announcer.farewell()

    assert generator.texts == ["Bye"]
    assert player.played[0].data == b"audio:Bye"


def test_empty_greeting_is_silent() -> None:
    announcer, generator, player = build_announcer(greeting="")

    announcer.greet()

    assert generator.texts == []
    assert player.played == []


def test_prepare_renders_both_clips_without_playing() -> None:
    announcer, generator, player = build_announcer()

    announcer.prepare()

    assert sorted(generator.texts) == ["Bye", "Hi"]
    assert player.played == []
