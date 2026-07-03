"""Wiring the gate to the announcer and the realtime session controller."""

from __future__ import annotations

import json

import pytest

from kel.config.settings import ConfigurationError, Settings
from kel.wake.app import (
    _vosk_grammar,
    _vosk_phrases,
    build_attention_gate,
    build_detector,
    validate_wake_settings,
)
from kel.wake.contracts import AttentionState, Phrase
from kel.wake.porcupine_detector import PorcupineWakeWordDetector
from kel.wake.vosk_detector import VoskWakeWordDetector


def make_settings(**overrides: str) -> Settings:
    values = {"OPENAI_API_KEY": "test-key"}
    values.update(overrides)
    return Settings.from_mapping(values)


def porcupine_settings(**overrides: str) -> Settings:
    base = {"KEL_WAKE_BACKEND": "porcupine"}
    base.update(overrides)
    return make_settings(**base)


def test_validation_requires_a_vosk_model_when_enabled() -> None:
    settings = make_settings()  # default backend is vosk

    with pytest.raises(ConfigurationError, match="VOSK_MODEL_PATH"):
        validate_wake_settings(settings)


def test_validation_passes_for_vosk_with_a_model_path() -> None:
    settings = make_settings(KEL_WAKE_VOSK_MODEL_PATH="/models/vosk-en")

    validate_wake_settings(settings)  # must not raise


def test_validation_requires_an_access_key_for_porcupine() -> None:
    settings = porcupine_settings(
        KEL_WAKE_KEYWORD_ATTENTION_PATH="attention.ppn",
        KEL_WAKE_KEYWORD_AT_EASE_PATH="at_ease.ppn",
    )

    with pytest.raises(ConfigurationError, match="WAKE_ACCESS_KEY"):
        validate_wake_settings(settings)


def test_validation_requires_keyword_paths_for_porcupine() -> None:
    settings = porcupine_settings(KEL_WAKE_ACCESS_KEY="pv-key")

    with pytest.raises(ConfigurationError, match="KEYWORD"):
        validate_wake_settings(settings)


def test_validation_is_skipped_when_disabled() -> None:
    settings = make_settings(KEL_WAKE_ENABLED="false")

    validate_wake_settings(settings)  # must not raise


class FakePorcupineEngine:
    sample_rate = 16_000
    frame_length = 4

    def process(self, _frame: object) -> int:
        return -1

    def delete(self) -> None:
        pass


class FakeVoskRecognizer:
    def AcceptWaveform(self, _data: bytes) -> bool:
        return False

    def Result(self) -> str:
        return "{}"

    def PartialResult(self) -> str:
        return "{}"


def test_build_detector_selects_the_vosk_backend() -> None:
    settings = make_settings(KEL_WAKE_VOSK_MODEL_PATH="/models/vosk-en")

    detector = build_detector(settings, lambda _p: None, recognizer=FakeVoskRecognizer())

    assert isinstance(detector, VoskWakeWordDetector)


def test_build_detector_selects_the_porcupine_backend() -> None:
    settings = porcupine_settings(
        KEL_WAKE_ACCESS_KEY="pv-key",
        KEL_WAKE_KEYWORD_ATTENTION_PATH="a.ppn",
        KEL_WAKE_KEYWORD_AT_EASE_PATH="b.ppn",
    )

    detector = build_detector(settings, lambda _p: None, engine=FakePorcupineEngine())

    assert isinstance(detector, PorcupineWakeWordDetector)


def test_every_configured_phrase_maps_to_its_action() -> None:
    settings = make_settings(
        KEL_WAKE_PHRASES_WAKE="wake up, you there",
        KEL_WAKE_PHRASES_SLEEP="go to sleep, good night, that is all",
    )

    mapping = _vosk_phrases(settings)

    assert mapping["wake up"] is Phrase.PAY_ATTENTION
    assert mapping["you there"] is Phrase.PAY_ATTENTION
    assert mapping["go to sleep"] is Phrase.AT_EASE
    assert mapping["good night"] is Phrase.AT_EASE
    assert mapping["that is all"] is Phrase.AT_EASE


def test_grammar_lists_every_phrase_with_the_name_and_a_catch_all() -> None:
    settings = make_settings(
        KEL_WAKE_PHRASES_WAKE="wake up",
        KEL_WAKE_PHRASES_SLEEP="good night",
    )

    grammar = _vosk_grammar(settings)

    assert "kel wake up" in grammar
    assert "kel good night" in grammar
    assert "[unk]" in grammar


def test_bare_name_wakes_and_is_matched_last() -> None:
    settings = make_settings(KEL_WAKE_PHRASES_SLEEP="at ease")

    mapping = _vosk_phrases(settings)

    assert mapping["kel"] is Phrase.PAY_ATTENTION  # calling her name wakes her
    # "kel" must be checked after the sleep phrase, or it would shadow it.
    assert list(mapping)[-1] == "kel"


def test_grammar_includes_the_bare_name_for_quick_mode() -> None:
    settings = make_settings()

    grammar = json.loads(_vosk_grammar(settings))

    assert "kel" in grammar


def test_quick_phrase_also_wakes_through_the_built_gate() -> None:
    log: list[str] = []
    settings = make_settings()
    gate = build_attention_gate(
        settings,
        announcer=FakeAnnouncer(log),
        session_controller=FakeSessionController(log),
    )

    gate.handle_phrase(Phrase.QUICK)

    assert gate.state is AttentionState.AWAKE
    assert log == ["greet", "start"]


class FakeAnnouncer:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    def prepare(self) -> None:
        self._log.append("prepare")

    def greet(self) -> None:
        self._log.append("greet")

    def farewell(self) -> None:
        self._log.append("farewell")


class FakeSessionController:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    def start(self) -> None:
        self._log.append("start")

    def stop(self) -> None:
        self._log.append("stop")


def test_waking_greets_then_starts_the_session() -> None:
    log: list[str] = []
    settings = make_settings()
    gate = build_attention_gate(
        settings,
        announcer=FakeAnnouncer(log),
        session_controller=FakeSessionController(log),
    )

    gate.handle_phrase(Phrase.PAY_ATTENTION)

    assert gate.state is AttentionState.AWAKE
    assert log == ["greet", "start"]


def test_sleeping_stops_the_session_then_says_farewell() -> None:
    log: list[str] = []
    settings = make_settings()
    gate = build_attention_gate(
        settings,
        announcer=FakeAnnouncer(log),
        session_controller=FakeSessionController(log),
    )
    gate.handle_phrase(Phrase.PAY_ATTENTION)
    log.clear()

    gate.handle_phrase(Phrase.AT_EASE)

    assert gate.state is AttentionState.ASLEEP
    assert log == ["stop", "farewell"]


class ManualClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_auto_sleep_is_silent() -> None:
    log: list[str] = []
    clock = ManualClock()
    settings = make_settings(KEL_WAKE_AUTO_SLEEP_SECONDS="5")
    gate = build_attention_gate(
        settings,
        announcer=FakeAnnouncer(log),
        session_controller=FakeSessionController(log),
        clock=clock,
    )
    gate.handle_phrase(Phrase.PAY_ATTENTION)
    log.clear()

    clock.advance(6.0)
    gate.check_timeout()

    assert gate.state is AttentionState.ASLEEP
    assert log == ["stop"]  # stops the session, but says nothing
