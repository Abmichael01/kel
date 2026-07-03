"""The Porcupine adapter maps engine keyword hits to Kel's trigger phrases."""

from __future__ import annotations

from array import array

from kel.wake.contracts import Phrase
from kel.wake.porcupine_detector import PorcupineWakeWordDetector


class FakeEngine:
    """Stands in for a pvporcupine handle without any audio or model."""

    sample_rate = 16_000
    frame_length = 4

    def __init__(self, results: list[int]) -> None:
        self._results = results
        self.processed: list[list[int]] = []
        self.deleted = False

    def process(self, frame: object) -> int:
        self.processed.append(list(frame))  # type: ignore[arg-type]
        return self._results.pop(0) if self._results else -1

    def delete(self) -> None:
        self.deleted = True


def build_detector(
    results: list[int],
) -> tuple[PorcupineWakeWordDetector, FakeEngine, list[Phrase]]:
    engine = FakeEngine(results)
    heard: list[Phrase] = []
    detector = PorcupineWakeWordDetector(
        engine=engine,
        phrases=(Phrase.PAY_ATTENTION, Phrase.AT_EASE),
        on_phrase=heard.append,
    )
    return detector, engine, heard


def test_keyword_index_zero_reports_pay_attention() -> None:
    detector, _, heard = build_detector([0])

    detector.process_frame([1, 2, 3, 4])

    assert heard == [Phrase.PAY_ATTENTION]


def test_keyword_index_one_reports_at_ease() -> None:
    detector, _, heard = build_detector([1])

    detector.process_frame([1, 2, 3, 4])

    assert heard == [Phrase.AT_EASE]


def test_no_keyword_reports_nothing() -> None:
    detector, _, heard = build_detector([-1])

    detector.process_frame([0, 0, 0, 0])

    assert heard == []


def test_feed_decodes_raw_pcm_bytes_into_a_frame() -> None:
    detector, engine, heard = build_detector([0])

    detector.feed(array("h", [5, 6, 7, 8]).tobytes())

    assert engine.processed == [[5, 6, 7, 8]]
    assert heard == [Phrase.PAY_ATTENTION]


def test_stop_releases_the_engine() -> None:
    detector, engine, _ = build_detector([])

    detector.stop()

    assert engine.deleted is True
