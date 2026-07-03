"""The attention gate decides when Kel is allowed to hear the cloud model."""

from __future__ import annotations

from kel.wake.contracts import AttentionState, Phrase, SleepReason
from kel.wake.gate import AttentionGate


class ManualClock:
    """A clock the tests advance by hand instead of waiting for real time."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def build_gate(
    *,
    auto_sleep_seconds: float = 90.0,
    quick_sleep_seconds: float = 15.0,
    clock: ManualClock | None = None,
) -> tuple[AttentionGate, list[str], list[SleepReason]]:
    woke: list[str] = []
    slept: list[SleepReason] = []
    gate = AttentionGate(
        auto_sleep_seconds=auto_sleep_seconds,
        quick_sleep_seconds=quick_sleep_seconds,
        on_wake=lambda: woke.append("wake"),
        on_sleep=slept.append,
        clock=clock or ManualClock(),
    )
    return gate, woke, slept


def test_gate_starts_asleep() -> None:
    gate, _, _ = build_gate()

    assert gate.state is AttentionState.ASLEEP


def test_pay_attention_wakes_the_gate() -> None:
    gate, woke, _ = build_gate()

    gate.handle_phrase(Phrase.PAY_ATTENTION)

    assert gate.state is AttentionState.AWAKE
    assert woke == ["wake"]


def test_at_ease_sleeps_the_gate() -> None:
    gate, _, slept = build_gate()
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    gate.handle_phrase(Phrase.AT_EASE)

    assert gate.state is AttentionState.ASLEEP
    assert slept == [SleepReason.AT_EASE]


def test_pay_attention_is_ignored_while_awake() -> None:
    gate, woke, _ = build_gate()
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    gate.handle_phrase(Phrase.PAY_ATTENTION)

    assert gate.state is AttentionState.AWAKE
    assert woke == ["wake"]


def test_at_ease_is_ignored_while_asleep() -> None:
    gate, _, slept = build_gate()

    gate.handle_phrase(Phrase.AT_EASE)

    assert gate.state is AttentionState.ASLEEP
    assert slept == []


def test_gate_auto_sleeps_after_silence() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=90.0, clock=clock)
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    clock.advance(89.0)
    gate.check_timeout()
    assert gate.state is AttentionState.AWAKE

    clock.advance(2.0)
    gate.check_timeout()

    assert gate.state is AttentionState.ASLEEP
    assert slept == [SleepReason.TIMEOUT]


def test_user_speech_postpones_auto_sleep() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=90.0, clock=clock)
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    clock.advance(80.0)
    gate.note_user_speech()  # resets the 90s window
    clock.advance(80.0)
    gate.check_timeout()

    assert gate.state is AttentionState.AWAKE
    assert slept == []


def test_zero_seconds_disables_auto_sleep() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=0.0, clock=clock)
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    clock.advance(10_000.0)
    gate.check_timeout()

    assert gate.state is AttentionState.AWAKE
    assert slept == []


def test_note_user_speech_is_ignored_while_asleep() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=90.0, clock=clock)

    gate.note_user_speech()
    clock.advance(1_000.0)
    gate.check_timeout()

    assert gate.state is AttentionState.ASLEEP
    assert slept == []


def test_quick_phrase_wakes_with_the_short_timeout() -> None:
    clock = ManualClock()
    gate, woke, slept = build_gate(auto_sleep_seconds=90.0, quick_sleep_seconds=15.0, clock=clock)

    gate.handle_phrase(Phrase.QUICK)
    assert gate.state is AttentionState.AWAKE
    assert woke == ["wake"]

    clock.advance(16.0)
    gate.check_timeout()

    assert gate.state is AttentionState.ASLEEP
    assert slept == [SleepReason.TIMEOUT]


def test_long_wake_outlives_the_quick_timeout() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=90.0, quick_sleep_seconds=15.0, clock=clock)

    gate.handle_phrase(Phrase.PAY_ATTENTION)
    clock.advance(16.0)  # past the quick window, well inside the long one
    gate.check_timeout()

    assert gate.state is AttentionState.AWAKE
    assert slept == []


def test_user_speech_upgrades_a_quick_wake_to_the_full_window() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=180.0, quick_sleep_seconds=15.0, clock=clock)
    gate.handle_phrase(Phrase.QUICK)  # quick wake: 15s window

    gate.note_user_speech()  # the user actually engages -> full window
    clock.advance(16.0)  # past the old quick window
    gate.check_timeout()
    assert gate.state is AttentionState.AWAKE
    assert slept == []

    clock.advance(170.0)  # now past the full 180s since that speech
    gate.check_timeout()
    assert gate.state is AttentionState.ASLEEP


def test_quick_phrase_is_ignored_while_already_awake() -> None:
    gate, woke, _ = build_gate()
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    gate.handle_phrase(Phrase.QUICK)

    assert gate.state is AttentionState.AWAKE
    assert woke == ["wake"]


def test_gate_can_wake_sleep_and_wake_again() -> None:
    gate, woke, slept = build_gate()

    gate.handle_phrase(Phrase.PAY_ATTENTION)
    gate.handle_phrase(Phrase.AT_EASE)
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    assert gate.state is AttentionState.AWAKE
    assert woke == ["wake", "wake"]
    assert slept == [SleepReason.AT_EASE]


def test_repeated_at_ease_only_sleeps_once() -> None:
    gate, _, slept = build_gate()
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    gate.handle_phrase(Phrase.AT_EASE)
    gate.handle_phrase(Phrase.AT_EASE)

    assert gate.state is AttentionState.ASLEEP
    assert slept == [SleepReason.AT_EASE]


def test_auto_sleep_timer_resets_after_a_fresh_wake() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=90.0, clock=clock)

    gate.handle_phrase(Phrase.PAY_ATTENTION)
    gate.handle_phrase(Phrase.AT_EASE)  # sleeps immediately
    clock.advance(200.0)  # long past the first wake's deadline
    gate.handle_phrase(Phrase.PAY_ATTENTION)  # fresh wake, fresh 90s window
    gate.check_timeout()

    assert gate.state is AttentionState.AWAKE
    assert slept == [SleepReason.AT_EASE]


def test_no_stale_timeout_fires_after_sleeping() -> None:
    clock = ManualClock()
    gate, _, slept = build_gate(auto_sleep_seconds=90.0, clock=clock)
    gate.handle_phrase(Phrase.PAY_ATTENTION)

    gate.handle_phrase(Phrase.AT_EASE)  # sleep before the deadline
    clock.advance(1_000.0)
    gate.check_timeout()  # must not sleep a second time

    assert gate.state is AttentionState.ASLEEP
    assert slept == [SleepReason.AT_EASE]
