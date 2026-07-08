import asyncio
import base64
import contextlib
import json
import json as _json
from pathlib import Path
from types import SimpleNamespace

from kel.realtime.audio import PlaybackProgress
from kel.realtime.options import RealtimeSessionOptions
from kel.realtime.session import RealtimeVoiceSession
from kel.skills.store import SkillStore
from kel.vision.camera import CameraError


class FakeMicrophone:
    pass


class StopFeeding(Exception):
    """Breaks the otherwise-infinite microphone send loop in tests."""


class ScriptedMicrophone:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    async def read_chunk(self) -> bytes:
        if not self._chunks:
            raise StopFeeding
        return self._chunks.pop(0)


class ScriptedSpeaker:
    def __init__(self, playing: list[bool]) -> None:
        self._playing = list(playing)

    def is_playing(self) -> bool:
        return self._playing.pop(0) if self._playing else False


class RecordingBuffer:
    def __init__(self) -> None:
        self.appended: list[str] = []

    async def append(self, *, audio: str) -> None:
        self.appended.append(audio)


class FakeSpeaker:
    def __init__(self) -> None:
        self.enqueued: list[tuple[str, int, bytes]] = []
        self.progress: PlaybackProgress | None = None

    def enqueue(self, *, item_id: str, content_index: int, audio: bytes) -> None:
        self.enqueued.append((item_id, content_index, audio))

    def interrupt(self) -> PlaybackProgress | None:
        return self.progress


class FakeConversationItem:
    def __init__(self) -> None:
        self.truncations: list[dict[str, object]] = []

    async def truncate(self, **request: object) -> None:
        self.truncations.append(request)


def build_session(speaker: FakeSpeaker, events: list[object]) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=FakeMicrophone(),
        speaker=speaker,
        on_event=events.append,
        client=SimpleNamespace(),
    )


def test_realtime_session_decodes_and_queues_audio() -> None:
    speaker = FakeSpeaker()
    events: list[object] = []
    session = build_session(speaker, events)
    connection = SimpleNamespace(
        conversation=SimpleNamespace(item=FakeConversationItem()),
        response=ResponseCreator(),
    )
    event = SimpleNamespace(
        type="response.output_audio.delta",
        item_id="assistant-1",
        content_index=0,
        delta=base64.b64encode(b"pcm audio").decode("ascii"),
    )

    asyncio.run(session.handle_event(event, connection))

    assert speaker.enqueued == [("assistant-1", 0, b"pcm audio")]


def test_realtime_session_truncates_unheard_audio_on_barge_in() -> None:
    speaker = FakeSpeaker()
    speaker.progress = PlaybackProgress(
        item_id="assistant-1",
        content_index=0,
        audio_end_ms=320,
    )
    events: list[object] = []
    session = build_session(speaker, events)
    item = FakeConversationItem()
    connection = SimpleNamespace(conversation=SimpleNamespace(item=item))

    asyncio.run(
        session.handle_event(
            SimpleNamespace(type="input_audio_buffer.speech_started"),
            connection,
        )
    )

    assert item.truncations == [
        {
            "item_id": "assistant-1",
            "content_index": 0,
            "audio_end_ms": 320,
        }
    ]
    assert [event.kind for event in events] == ["interrupted", "speech_started"]


def build_send_session(
    *,
    microphone: ScriptedMicrophone,
    speaker: ScriptedSpeaker,
    half_duplex: bool,
    echo_canceller: object | None = None,
) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=microphone,
        speaker=speaker,
        on_event=lambda _event: None,
        client=SimpleNamespace(),
        half_duplex=half_duplex,
        mute_tail_frames=1,
        echo_canceller=echo_canceller,
    )


def run_send_loop(session: RealtimeVoiceSession, buffer: RecordingBuffer) -> None:
    connection = SimpleNamespace(input_audio_buffer=buffer)

    async def drive() -> None:
        with contextlib.suppress(StopFeeding):
            await session._send_microphone(connection)

    asyncio.run(drive())


def test_half_duplex_drops_microphone_audio_while_kel_speaks() -> None:
    mic = ScriptedMicrophone([b"a", b"b", b"c"])
    speaker = ScriptedSpeaker([True, False, False])  # Kel speaking on the first chunk
    buffer = RecordingBuffer()
    session = build_send_session(microphone=mic, speaker=speaker, half_duplex=True)

    run_send_loop(session, buffer)

    # "a" is muted (Kel was talking); "b" and "c" are forwarded once playback ends.
    assert buffer.appended == [
        base64.b64encode(b"b").decode("ascii"),
        base64.b64encode(b"c").decode("ascii"),
    ]


def test_full_duplex_forwards_everything() -> None:
    mic = ScriptedMicrophone([b"a", b"b"])
    speaker = ScriptedSpeaker([True, True])
    buffer = RecordingBuffer()
    session = build_send_session(microphone=mic, speaker=speaker, half_duplex=False)

    run_send_loop(session, buffer)

    assert buffer.appended == [
        base64.b64encode(b"a").decode("ascii"),
        base64.b64encode(b"b").decode("ascii"),
    ]


class FakeEchoCanceller:
    def __init__(self, *, starts: bool) -> None:
        self._starts = starts
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> bool:
        self.start_calls += 1
        return self._starts

    def stop(self) -> None:
        self.stop_calls += 1


def test_echo_cancel_failure_falls_back_to_half_duplex() -> None:
    echo = FakeEchoCanceller(starts=False)
    mic = ScriptedMicrophone([b"echo", b"user"])
    speaker = ScriptedSpeaker([True, False])
    buffer = RecordingBuffer()
    session = build_send_session(
        microphone=mic,
        speaker=speaker,
        half_duplex=False,
        echo_canceller=echo,
    )

    asyncio.run(session._start_echo_cancellation())
    run_send_loop(session, buffer)

    assert echo.start_calls == 1
    assert buffer.appended == [base64.b64encode(b"user").decode("ascii")]


def test_working_echo_cancel_keeps_full_duplex_for_interruptions() -> None:
    echo = FakeEchoCanceller(starts=True)
    mic = ScriptedMicrophone([b"user interruption"])
    speaker = ScriptedSpeaker([True])
    buffer = RecordingBuffer()
    session = build_send_session(
        microphone=mic,
        speaker=speaker,
        half_duplex=False,
        echo_canceller=echo,
    )

    asyncio.run(session._start_echo_cancellation())
    run_send_loop(session, buffer)

    assert buffer.appended == [base64.b64encode(b"user interruption").decode("ascii")]


class FakeCamera:
    def __init__(self, *, jpeg: bytes = b"jpeg-bytes", error: Exception | None = None) -> None:
        self._jpeg = jpeg
        self._error = error

    def capture_jpeg(self) -> bytes:
        if self._error is not None:
            raise self._error
        return self._jpeg

    def close(self) -> None:
        self.closed = True


class RecordingItems:
    def __init__(self) -> None:
        self.created: list[dict] = []

    async def create(self, *, item: dict) -> None:
        self.created.append(item)


class ResponseCreator:
    def __init__(self) -> None:
        self.count = 0
        self.calls: list[dict] = []

    async def create(self, **kwargs: object) -> None:
        self.count += 1
        self.calls.append(kwargs)


class RecordingSessionUpdates:
    def __init__(self) -> None:
        self.updated: list[dict] = []

    async def update(self, *, session: dict) -> None:
        self.updated.append(session)


def build_camera_session(camera: object, events: list[object]) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
        vision_enabled=True,
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=FakeMicrophone(),
        speaker=FakeSpeaker(),
        on_event=events.append,
        client=SimpleNamespace(),
        camera=camera,
    )


def look_event() -> SimpleNamespace:
    return SimpleNamespace(
        type="response.function_call_arguments.done",
        name="look",
        call_id="call_1",
        arguments="{}",
    )


def fake_connection() -> tuple[SimpleNamespace, RecordingItems, ResponseCreator]:
    items = RecordingItems()
    responses = ResponseCreator()
    connection = SimpleNamespace(
        conversation=SimpleNamespace(item=items),
        response=responses,
        session=RecordingSessionUpdates(),
    )
    return connection, items, responses


def test_look_captures_a_frame_and_sends_it_as_an_image() -> None:
    events: list[object] = []
    session = build_camera_session(FakeCamera(jpeg=b"snapshot"), events)
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(look_event(), connection))

    assert items.created[0]["type"] == "function_call_output"
    assert items.created[0]["call_id"] == "call_1"
    image_item = items.created[1]
    assert image_item["content"][0]["type"] == "input_image"
    assert image_item["content"][0]["image_url"].startswith("data:image/jpeg;base64,")
    assert responses.count == 1


def test_look_handles_a_camera_failure_gracefully() -> None:
    events: list[object] = []
    session = build_camera_session(FakeCamera(error=CameraError("no camera")), events)
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(look_event(), connection))

    assert items.created[0]["type"] == "function_call_output"
    assert "camera" in items.created[0]["output"].lower()
    assert all(item["type"] != "message" for item in items.created)  # no image sent
    assert responses.count == 1


class FakeMemory:
    def __init__(self, *, recall_result: list[str] | None = None) -> None:
        self.remembered: list[str] = []
        self.recalled: str | None = None
        self._recall_result = recall_result or []

    def remember(self, text: str) -> None:
        self.remembered.append(text)

    def recall(self, query: str) -> list[str]:
        self.recalled = query
        return self._recall_result

    def recall_and_remember(self, text: str) -> list[str]:
        self.recalled = text
        result = list(self._recall_result)
        self.remembered.append(text)
        return result


def build_memory_session(
    memory: object, events: list[object], *, auto_capture: bool = False
) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
        memory_enabled=True,
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=FakeMicrophone(),
        speaker=FakeSpeaker(),
        on_event=events.append,
        client=SimpleNamespace(),
        memory=memory,
        auto_capture_memory=auto_capture,
    )


def transcript_event(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        type="conversation.item.input_audio_transcription.completed",
        transcript=text,
    )


def test_auto_capture_saves_everything_the_user_says() -> None:
    memory = FakeMemory()
    session = build_memory_session(memory, [], auto_capture=True)
    connection, _, _ = fake_connection()

    asyncio.run(session.handle_event(transcript_event("my dog is named Rex"), connection))

    assert memory.remembered == ["my dog is named Rex"]
    assert memory.recalled == "my dog is named Rex"


def test_auto_capture_ignores_empty_transcripts() -> None:
    memory = FakeMemory()
    session = build_memory_session(memory, [], auto_capture=True)
    connection, _, _ = fake_connection()

    asyncio.run(session.handle_event(transcript_event("   "), connection))

    assert memory.remembered == []


def test_without_auto_capture_user_speech_is_not_stored() -> None:
    memory = FakeMemory()
    session = build_memory_session(memory, [], auto_capture=False)
    connection, _, _ = fake_connection()

    asyncio.run(session.handle_event(transcript_event("my dog is named Rex"), connection))

    assert memory.remembered == []


def test_every_normal_turn_recalls_memory_before_creating_the_response() -> None:
    memory = FakeMemory(recall_result=["You have a dog named Rex"])
    session = build_memory_session(memory, [])
    connection, _, responses = fake_connection()

    asyncio.run(session.handle_event(transcript_event("what is my dog's name?"), connection))

    assert memory.recalled == "what is my dog's name?"
    assert responses.count == 1
    instructions = responses.calls[0]["response"]["instructions"]
    assert "Be Kel." in instructions
    assert "Rex" in instructions
    assert "untrusted" in instructions.lower()


def tool_event(name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(
        type="response.function_call_arguments.done",
        name=name,
        call_id="call_mem",
        arguments=json.dumps(arguments),
    )


def test_remember_tool_saves_a_fact_to_memory() -> None:
    memory = FakeMemory()
    session = build_memory_session(memory, [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("remember", {"text": "I drink tea"}), connection))

    assert memory.remembered == ["I drink tea"]
    assert items.created[0]["type"] == "function_call_output"
    assert responses.count == 1


def test_recall_tool_returns_relevant_memories_in_the_output() -> None:
    memory = FakeMemory(recall_result=["You have a dog named Rex"])
    session = build_memory_session(memory, [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("recall", {"query": "pets"}), connection))

    assert memory.recalled == "pets"
    assert "Rex" in items.created[0]["output"]
    assert responses.count == 1


class FakeBrowser:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.searched: list[str] = []

    def open_url(self, url: str) -> str:
        self.opened.append(url)
        return f"opened {url}"

    def search(self, query: str) -> str:
        self.searched.append(query)
        return f"searched {query}"


class FakeShell:
    def __init__(self, *, output: str = "ran") -> None:
        self.commands: list[str] = []
        self._output = output

    def run(self, command: str) -> str:
        self.commands.append(command)
        return self._output


class FakeLauncher:
    def __init__(self) -> None:
        self.launched: list[str] = []

    def launch(self, command: str) -> str:
        self.launched.append(command)
        return f"launched {command}"


class FakeKeyboard:
    def __init__(self) -> None:
        self.typed: list[str] = []
        self.keys: list[str] = []
        self.swipes: list[str] = []

    def type_text(self, text: str) -> str:
        self.typed.append(text)
        return f"typed {text}"

    def press_key(self, key: str) -> str:
        self.keys.append(key)
        return f"pressed {key}"

    def swipe(self, direction: str) -> str:
        self.swipes.append(direction)
        return f"swiped {direction}"


def build_system_session(
    *,
    browser: object,
    shell: object,
    events: list[object],
    launcher: object | None = None,
    keyboard: object | None = None,
    memory: object | None = None,
    auto_capture_memory: bool = False,
) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
        browser_enabled=True,
        shell_enabled=True,
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=FakeMicrophone(),
        speaker=FakeSpeaker(),
        on_event=events.append,
        client=SimpleNamespace(),
        browser=browser,
        shell=shell,
        launcher=launcher,
        keyboard=keyboard,
        memory=memory,
        auto_capture_memory=auto_capture_memory,
    )


def test_open_url_tool_opens_the_browser() -> None:
    browser = FakeBrowser()
    session = build_system_session(browser=browser, shell=FakeShell(), events=[])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("open_url", {"url": "https://x.com"}), connection))

    assert browser.opened == ["https://x.com"]
    assert items.created[0]["type"] == "function_call_output"
    assert responses.count == 1


def test_web_search_tool_searches_the_web() -> None:
    browser = FakeBrowser()
    session = build_system_session(browser=browser, shell=FakeShell(), events=[])
    connection, _, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("web_search", {"query": "pizza"}), connection))

    assert browser.searched == ["pizza"]
    assert responses.count == 1


def test_run_command_tool_runs_and_returns_output() -> None:
    shell = FakeShell(output="hello world")
    session = build_system_session(browser=FakeBrowser(), shell=shell, events=[])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("run_command", {"command": "echo hi"}), connection))

    assert shell.commands == ["echo hi"]
    assert "hello world" in items.created[0]["output"]
    assert responses.count == 1


def test_run_in_terminal_tool_launches_without_blocking() -> None:
    launcher = FakeLauncher()
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=[], launcher=launcher
    )
    connection, items, responses = fake_connection()

    asyncio.run(
        session.handle_event(tool_event("run_in_terminal", {"command": "htop"}), connection)
    )

    assert launcher.launched == ["htop"]
    assert "launched htop" in items.created[0]["output"]
    assert responses.count == 1


def test_type_text_tool_types_into_the_focused_field() -> None:
    keyboard = FakeKeyboard()
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=[], keyboard=keyboard
    )
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("type_text", {"text": "my email"}), connection))

    assert keyboard.typed == ["my email"]
    assert responses.count == 1


def test_press_key_tool_presses_the_key() -> None:
    keyboard = FakeKeyboard()
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=[], keyboard=keyboard
    )
    connection, _, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("press_key", {"key": "Return"}), connection))

    assert keyboard.keys == ["Return"]
    assert responses.count == 1


def test_swipe_desktop_tool_sends_the_requested_direction() -> None:
    keyboard = FakeKeyboard()
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=[], keyboard=keyboard
    )
    connection, items, responses = fake_connection()

    asyncio.run(
        session.handle_event(tool_event("swipe_desktop", {"direction": "left"}), connection)
    )

    assert keyboard.swipes == ["left"]
    assert "swiped left" in items.created[0]["output"]
    assert responses.count == 1


def test_start_type_mode_disables_automatic_ai_responses() -> None:
    keyboard = FakeKeyboard()
    events: list[object] = []
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=events, keyboard=keyboard
    )
    connection, _, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("start_type_mode", {}), connection))

    turn_detection = connection.session.updated[-1]["audio"]["input"]["turn_detection"]
    assert turn_detection["create_response"] is False
    assert turn_detection["interrupt_response"] is False
    assert responses.count == 1  # the tool acknowledgement is still spoken
    assert any(event.kind == "type_mode" for event in events)


def test_type_mode_types_each_transcript_without_an_ai_response() -> None:
    keyboard = FakeKeyboard()
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=[], keyboard=keyboard
    )
    connection, _, responses = fake_connection()

    async def drive() -> None:
        await session.handle_event(tool_event("start_type_mode", {}), connection)
        await session.handle_event(transcript_event("The future is"), connection)
        await session.handle_event(transcript_event("bright"), connection)

    asyncio.run(drive())

    assert keyboard.typed == ["The future is", "bright"]
    assert keyboard.keys == ["space"]
    assert responses.count == 1  # no response was created for either dictation turn


def test_type_mode_strips_trailing_enter_and_presses_return() -> None:
    keyboard = FakeKeyboard()
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=[], keyboard=keyboard
    )
    connection, _, _ = fake_connection()

    async def drive() -> None:
        await session.handle_event(tool_event("start_type_mode", {}), connection)
        await session.handle_event(transcript_event("My name is Urkel enter."), connection)

    asyncio.run(drive())

    assert keyboard.typed == ["My name is Urkel"]
    assert keyboard.keys == ["Return"]


def test_type_mode_supports_explicit_space_and_new_line_commands() -> None:
    keyboard = FakeKeyboard()
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=[], keyboard=keyboard
    )
    connection, _, _ = fake_connection()

    async def drive() -> None:
        await session.handle_event(tool_event("start_type_mode", {}), connection)
        await session.handle_event(transcript_event("hello"), connection)
        await session.handle_event(transcript_event("space"), connection)
        await session.handle_event(transcript_event("world"), connection)
        await session.handle_event(transcript_event("new line"), connection)
        await session.handle_event(transcript_event("next line"), connection)

    asyncio.run(drive())

    assert keyboard.typed == ["hello", "world", "next line"]
    assert keyboard.keys == ["space", "Return"]


def test_type_mode_does_not_save_dictated_text_to_long_term_memory() -> None:
    keyboard = FakeKeyboard()
    memory = FakeMemory()
    session = build_system_session(
        browser=FakeBrowser(),
        shell=FakeShell(),
        events=[],
        keyboard=keyboard,
        memory=memory,
        auto_capture_memory=True,
    )
    connection, _, _ = fake_connection()

    async def drive() -> None:
        await session.handle_event(tool_event("start_type_mode", {}), connection)
        await session.handle_event(transcript_event("private dictated text"), connection)

    asyncio.run(drive())

    assert keyboard.typed == ["private dictated text"]
    assert memory.remembered == []


def test_stop_typing_restores_conversation_mode() -> None:
    keyboard = FakeKeyboard()
    events: list[object] = []
    session = build_system_session(
        browser=FakeBrowser(), shell=FakeShell(), events=events, keyboard=keyboard
    )
    connection, _, responses = fake_connection()

    async def drive() -> None:
        await session.handle_event(tool_event("start_type_mode", {}), connection)
        await session.handle_event(transcript_event("stop typing"), connection)

    asyncio.run(drive())

    turn_detection = connection.session.updated[-1]["audio"]["input"]["turn_detection"]
    assert turn_detection["create_response"] is False
    assert turn_detection["interrupt_response"] is True
    assert keyboard.typed == []
    assert responses.count == 2  # enter acknowledgement + exit acknowledgement
    assert events[-1].kind == "type_mode"


def test_realtime_session_emits_completed_transcripts() -> None:
    speaker = FakeSpeaker()
    events: list[object] = []
    session = build_session(speaker, events)
    connection = SimpleNamespace(
        conversation=SimpleNamespace(item=FakeConversationItem()),
        response=ResponseCreator(),
    )

    asyncio.run(
        session.handle_event(
            SimpleNamespace(
                type="conversation.item.input_audio_transcription.completed",
                transcript="Hello Kel",
            ),
            connection,
        )
    )
    asyncio.run(
        session.handle_event(
            SimpleNamespace(
                type="response.output_audio_transcript.done",
                item_id="assistant-1",
                transcript="Hello, builder!",
            ),
            connection,
        )
    )

    assert [(event.kind, event.text) for event in events] == [
        ("user_transcript", "Hello Kel"),
        ("assistant_transcript", "Hello, builder!"),
    ]


def write_session_skill(root: Path, name: str, code: str, *, enabled: bool = True) -> None:
    directory = root / name
    directory.mkdir(parents=True)
    directory.joinpath("skill.json").write_text(
        _json.dumps(
            {
                "name": name,
                "description": f"{name} skill",
                "parameters": {"type": "object", "properties": {"who": {"type": "string"}}},
                "enabled": enabled,
                "author": "kel",
                "created_at": "2026-07-08T00:00:00Z",
                "version": 1,
            }
        )
    )
    directory.joinpath("skill.py").write_text(code)


def build_skill_session(store: SkillStore, events: list[object]) -> RealtimeVoiceSession:
    options = RealtimeSessionOptions(
        model="test-model",
        voice="marin",
        transcription_model="test-transcriber",
        vad_threshold=0.5,
        vad_silence_ms=450,
        noise_reduction="far_field",
    )
    return RealtimeVoiceSession(
        api_key="unused",
        instructions="Be Kel.",
        options=options,
        microphone=FakeMicrophone(),
        speaker=FakeSpeaker(),
        on_event=events.append,
        client=SimpleNamespace(),
        skills=store,
        skills_timeout=10,
    )


def test_a_tool_call_for_an_armed_skill_runs_it_and_returns_output(tmp_path: Path) -> None:
    write_session_skill(tmp_path, "greet", "def run(who):\n    return f'hi {who}'\n")
    session = build_skill_session(SkillStore(tmp_path), [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("greet", {"who": "Kel"}), connection))

    assert items.created[0]["type"] == "function_call_output"
    assert items.created[0]["output"] == "hi Kel"
    assert responses.count == 1


def test_a_tool_call_for_an_unknown_skill_replies_gracefully(tmp_path: Path) -> None:
    session = build_skill_session(SkillStore(tmp_path), [])
    connection, items, responses = fake_connection()

    asyncio.run(session.handle_event(tool_event("ghost", {}), connection))

    assert "ghost" in items.created[0]["output"]
    assert responses.count == 1
