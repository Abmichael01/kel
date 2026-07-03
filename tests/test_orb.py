"""The orb animates a palette per mood and latches a feeling when asked."""

from __future__ import annotations

import asyncio

from kel.body.orb import MODES, BodyOrb


class FakeBody:
    def set_mode(self, name: str) -> None:
        pass


def make() -> BodyOrb:
    return BodyOrb(FakeBody())


def _drive(orb: BodyOrb, ticks: int) -> None:
    async def run() -> None:
        for _ in range(ticks):
            await orb._tick()

    asyncio.run(run())


def test_state_drives_mode_when_nothing_is_latched() -> None:
    orb = make()
    orb.set_state("thinking")
    assert orb.mode == "thinking"


def test_a_feeling_latches_and_survives_state_changes() -> None:
    orb = make()
    orb.set_feeling("sad")

    assert orb.mode == "sad"
    assert orb.latched

    orb.set_state("thinking")  # must be ignored while a feeling is latched
    assert orb.mode == "sad"


def test_sleep_clears_the_latch() -> None:
    orb = make()
    orb.set_feeling("sad")

    orb.sleep()

    assert orb.mode == "sleeping"
    assert not orb.latched
    orb.set_state("listening")
    assert orb.mode == "listening"


def test_normal_unlatches() -> None:
    orb = make()
    orb.set_feeling("sad")

    orb.set_feeling("normal")

    assert not orb.latched


def test_orb_resends_a_mode_until_the_board_acknowledges() -> None:
    class FlakyBody:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self._replies = iter(["", "", "ok"])  # lost while booting, then acked

        def set_mode(self, name: str) -> str:
            self.calls.append(name)
            return next(self._replies, "ok")

    body = FlakyBody()
    orb = BodyOrb(body)
    orb.set_state("listening")

    _drive(orb, ticks=3)

    assert body.calls == ["listening", "listening", "listening"]


def test_orb_stops_resending_once_acknowledged() -> None:
    class OkBody:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def set_mode(self, name: str) -> str:
            self.calls.append(name)
            return "ok"

    body = OkBody()
    orb = BodyOrb(body)
    orb.set_state("thinking")

    _drive(orb, ticks=4)

    assert body.calls == ["thinking"]  # acknowledged on the first push, never repeated


def test_orb_mirrors_each_mood_to_the_screen_face() -> None:
    class FakeFace:
        def __init__(self) -> None:
            self.moods: list[str] = []

        def set_mood(self, mood: str) -> None:
            self.moods.append(mood)

    face = FakeFace()
    orb = BodyOrb(None, face=face)  # no Arduino, so start() needs no event loop
    orb.start()  # pushes the initial mood
    orb.set_state("listening")
    orb.set_feeling("happy")
    orb.sleep()

    assert face.moods == ["sleeping", "listening", "happy", "sleeping"]


def test_all_expected_moods_are_known() -> None:
    moods = (
        "sleeping", "listening", "thinking", "typing",
        "happy", "sad", "excited", "playful", "love", "calm", "alert", "normal",
    )
    for mood in moods:
        assert mood in MODES
