"""The Vosk adapter recognizes trigger phrases inside local transcripts."""

from __future__ import annotations

import json

from kel.wake.contracts import Phrase
from kel.wake.vosk_detector import VoskWakeWordDetector


class FakeRecognizer:
    """A scripted stand-in for a Vosk KaldiRecognizer."""

    def __init__(self, script: list[dict[str, object]]) -> None:
        self._script = list(script)
        self._current: dict[str, object] = {"final": False, "text": ""}

    def AcceptWaveform(self, _data: bytes) -> bool:
        self._current = self._script.pop(0) if self._script else {"final": False, "text": ""}
        return bool(self._current["final"])

    def Result(self) -> str:
        return json.dumps({"text": self._current["text"]})

    def PartialResult(self) -> str:
        return json.dumps({"partial": self._current["text"]})


def build_detector(
    script: list[dict[str, object]],
) -> tuple[VoskWakeWordDetector, list[Phrase]]:
    heard: list[Phrase] = []
    detector = VoskWakeWordDetector(
        recognizer=FakeRecognizer(script),
        phrases={"pay attention": Phrase.PAY_ATTENTION, "at ease": Phrase.AT_EASE},
        on_phrase=heard.append,
    )
    return detector, heard


def test_final_transcript_with_pay_attention_wakes() -> None:
    detector, heard = build_detector([{"final": True, "text": "kel pay attention"}])

    detector.feed(b"\x00\x00")

    assert heard == [Phrase.PAY_ATTENTION]


def test_final_transcript_with_at_ease_sleeps() -> None:
    detector, heard = build_detector([{"final": True, "text": "okay kel at ease now"}])

    detector.feed(b"\x00\x00")

    assert heard == [Phrase.AT_EASE]


def test_unrelated_transcript_reports_nothing() -> None:
    detector, heard = build_detector([{"final": True, "text": "what time is it"}])

    detector.feed(b"\x00\x00")

    assert heard == []


def test_partial_results_are_ignored() -> None:
    detector, heard = build_detector([{"final": False, "text": "kel pay attention"}])

    detector.feed(b"\x00\x00")

    assert heard == []


def test_matching_is_case_insensitive() -> None:
    detector, heard = build_detector([{"final": True, "text": "KEL PAY ATTENTION"}])

    detector.feed(b"\x00\x00")

    assert heard == [Phrase.PAY_ATTENTION]


def test_several_phrases_can_map_to_the_same_action() -> None:
    heard: list[Phrase] = []
    detector = VoskWakeWordDetector(
        recognizer=FakeRecognizer(
            [
                {"final": True, "text": "kel wake up"},
                {"final": True, "text": "kel you there"},
                {"final": True, "text": "kel good night"},
            ]
        ),
        phrases={
            "wake up": Phrase.PAY_ATTENTION,
            "you there": Phrase.PAY_ATTENTION,
            "good night": Phrase.AT_EASE,
        },
        on_phrase=heard.append,
    )

    detector.feed(b"\x00\x00")
    detector.feed(b"\x00\x00")
    detector.feed(b"\x00\x00")

    assert heard == [Phrase.PAY_ATTENTION, Phrase.PAY_ATTENTION, Phrase.AT_EASE]


def test_matching_ignores_punctuation_like_apostrophes() -> None:
    heard: list[Phrase] = []
    detector = VoskWakeWordDetector(
        recognizer=FakeRecognizer([{"final": True, "text": "kel lets talk"}]),
        phrases={"let's talk": Phrase.PAY_ATTENTION},
        on_phrase=heard.append,
    )

    detector.feed(b"\x00\x00")

    assert heard == [Phrase.PAY_ATTENTION]
