"""Gemini Live speech-to-speech orchestration, mirroring the OpenAI session.

This speaks to Google's Gemini Live API instead of OpenAI's Realtime API, but it
reuses every other part of Kel: the same microphone/speaker, camera, memory, body,
orb, browser, shell and keyboard, the same tool set, and the same display events -
so the wake gate, the glowing orb and the LCD face behave identically.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import types

from kel.body.controller import BodyController
from kel.body.feelings import color_for
from kel.memory.store import MemoryStore
from kel.realtime.audio import StreamingMicrophone, StreamingSpeaker
from kel.realtime.dictation import parse_dictation
from kel.realtime.echo_cancel import PulseEchoCanceller
from kel.realtime.events import RealtimeDisplayEvent
from kel.realtime.gemini_tools import gemini_tools
from kel.realtime.options import (
    BUILD_SKILL_TOOL_NAME,
    LOOK_TOOL_NAME,
    MOVE_TOOL_NAME,
    OPEN_URL_TOOL_NAME,
    PRESS_KEY_TOOL_NAME,
    RECALL_TOOL_NAME,
    REMEMBER_TOOL_NAME,
    RUN_COMMAND_TOOL_NAME,
    RUN_IN_TERMINAL_TOOL_NAME,
    SEE_SCREEN_TOOL_NAME,
    SET_FEELING_TOOL_NAME,
    START_TYPE_MODE_TOOL_NAME,
    SWIPE_DESKTOP_TOOL_NAME,
    TYPE_TEXT_TOOL_NAME,
    WEB_SEARCH_TOOL_NAME,
    RealtimeSessionOptions,
)
from kel.skills.authoring.author import SkillAuthor
from kel.skills.executor import run_skill
from kel.skills.store import SkillStore
from kel.system.browser import Browser
from kel.system.keyboard import Keyboard
from kel.system.launcher import TerminalLauncher
from kel.system.shell import ShellRunner
from kel.vision.camera import Camera, CameraError
from kel.vision.screen import Screen, ScreenError

RealtimeEventHandler = Callable[[RealtimeDisplayEvent], None]

# Gemini Live requires 16 kHz PCM input and always returns 24 kHz PCM output.
GEMINI_INPUT_RATE = 16_000
GEMINI_OUTPUT_RATE = 24_000

_TONE_NOTE = (
    '\n\nYou sometimes receive a short note like "(voice tone: sounds quiet and '
    'subdued)" describing HOW the user sounds right now - their energy and pitch - '
    "since you otherwise only get their words. Read it together with what they say to "
    "sense their real mood, and respond to it warmly. Never read the note aloud or "
    "mention that you received it."
)


class GeminiVoiceSession:
    """Maintain one persistent Gemini Live speech-to-speech connection."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        voice: str,
        instructions: str,
        options: RealtimeSessionOptions,
        microphone: StreamingMicrophone,
        speaker: StreamingSpeaker,
        on_event: RealtimeEventHandler,
        affective_dialog: bool = False,
        tone_cues: bool = False,
        client: Any | None = None,
        half_duplex: bool = True,
        mute_tail_frames: int = 15,
        camera: Camera | None = None,
        screen: Screen | None = None,
        memory: MemoryStore | None = None,
        auto_capture_memory: bool = False,
        browser: Browser | None = None,
        shell: ShellRunner | None = None,
        launcher: TerminalLauncher | None = None,
        keyboard: Keyboard | None = None,
        echo_canceller: PulseEchoCanceller | None = None,
        body: BodyController | None = None,
        body_servo_pin: int = 9,
        close_body: bool = True,
        orb: Any | None = None,
        skills: SkillStore | None = None,
        skills_timeout: float = 20.0,
        author: SkillAuthor | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._voice = voice
        self._instructions = instructions
        self._options = options
        self._microphone = microphone
        self._speaker = speaker
        self._on_event = on_event
        self._affective_dialog = affective_dialog
        self._tone_cues = tone_cues
        self._prosody: Any | None = None
        if tone_cues:
            from kel.realtime.prosody import ProsodyReader

            self._prosody = ProsodyReader(GEMINI_INPUT_RATE)
        self._last_tone: str | None = None
        self._tone_cooldown = 0
        self._client = client
        self._half_duplex = half_duplex
        self._mute_tail_frames = mute_tail_frames
        self._camera = camera
        self._screen = screen
        self._memory = memory
        self._auto_capture_memory = auto_capture_memory
        self._browser = browser
        self._shell = shell
        self._launcher = launcher
        self._keyboard = keyboard
        self._echo_canceller = echo_canceller
        self._body = body
        self._body_servo_pin = body_servo_pin
        self._close_body = close_body
        self._orb = orb
        self._skills = skills
        self._skills_timeout = skills_timeout
        self._author = author
        self._session: Any | None = None
        self._user_buf = ""
        self._assistant_buf = ""
        self._user_turn_open = False
        self._turn_seq = 0
        self._type_mode = False
        self._type_mode_needs_separator = False
        self._speaking = False
        self._resume_handle: str | None = None
        self._bg_tasks: set[asyncio.Task[Any]] = set()

    def _build_config(self) -> types.LiveConnectConfig:
        """Assemble the Live config: voice, transcripts, tools, resumption, snappy VAD."""
        tools = gemini_tools([*self._options.tool_specs(), *self._skill_specs()])
        instructions = self._instructions + (_TONE_NOTE if self._tone_cues else "")
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=instructions,
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self._voice)
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            tools=tools or None,
            # Resume the same conversation after a drop instead of starting over.
            session_resumption=types.SessionResumptionConfig(handle=self._resume_handle),
            # Compress old context so long chats don't hit the limit and die mid-way.
            context_window_compression=types.ContextWindowCompressionConfig(
                trigger_tokens=25600,
                sliding_window=types.SlidingWindow(target_tokens=12800),
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    # LOW start = she needs clearer, more-confident speech before she reacts,
                    # so room noise or her own echo doesn't register as you talking (and stop
                    # her mid-sentence). This is the main "listen smarter" knob.
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    # HIGH end = still answers promptly once you actually stop.
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    silence_duration_ms=self._options.vad_silence_ms,
                    prefix_padding_ms=300,  # keep more lead-in so word onsets aren't clipped
                )
            ),
        )
        if self._affective_dialog:
            config.enable_affective_dialog = True
        return config

    async def run(self) -> None:
        """Open the mic/speaker once, then converse (reconnecting if the link drops)."""
        # Affective dialog (reacting to your tone) is only served on the v1alpha endpoint.
        api_version = "v1alpha" if self._affective_dialog else "v1beta"
        client = self._client or genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(api_version=api_version),
        )
        speaker_started = microphone_started = echo_started = False
        try:
            echo_started = await self._start_echo_cancellation()
            self._speaker.start()
            speaker_started = True
            self._microphone.start()
            microphone_started = True
            await self._converse(client)
        finally:
            if microphone_started:
                self._microphone.stop()
            if speaker_started:
                self._speaker.stop()
            if echo_started and self._echo_canceller is not None:
                await asyncio.to_thread(self._echo_canceller.stop)
            if self._camera is not None:
                self._camera.close()
            if self._body is not None and self._close_body:
                self._body.close()

    async def _converse(self, client: Any) -> None:
        """Keep a Live session running, transparently reconnecting on a dropped link.

        Gemini Live sessions are time-limited and the server can end one mid-chat; with
        session resumption we reconnect and carry on instead of going dead. We only give
        up if it fails to stay connected several times in a row (a real config problem).
        """
        loop = asyncio.get_running_loop()
        quick_failures = 0
        first = True
        while True:
            self._reset_turn()
            started = loop.time()
            try:
                async with client.aio.live.connect(
                    model=self._model, config=self._build_config()
                ) as session:
                    self._session = session
                    self._emit(
                        "connected",
                        "Live connection ready. Speak naturally."
                        if first
                        else "Reconnected — keep going.",
                    )
                    first = False
                    if self._orb is not None:
                        self._orb.set_state("listening")
                    async with asyncio.TaskGroup() as tasks:
                        tasks.create_task(self._send_microphone(session))
                        tasks.create_task(self._receive_events(session))
                return
            except* Exception as group:  # noqa: BLE001 - reconnect on a dropped link
                error = group.exceptions[0]
                quick_failures = quick_failures + 1 if loop.time() - started < 3.0 else 0
                if quick_failures >= 3:
                    self._emit(
                        "error",
                        "Gemini Live keeps dropping (check KEL_GEMINI_REALTIME_MODEL and "
                        f"GEMINI_API_KEY): {error}",
                    )
                    raise
                self._emit("connected", "Connection dropped — reconnecting...")
                await asyncio.sleep(0.6)

    def _reset_turn(self) -> None:
        """Clear per-turn state so a reconnect starts clean."""
        self._user_buf = ""
        self._assistant_buf = ""
        self._user_turn_open = False
        self._speaking = False
        self._last_tone = None
        self._tone_cooldown = 0

    async def _start_echo_cancellation(self) -> bool:
        """Enable AEC or fall back to loop-safe half-duplex audio."""
        if self._echo_canceller is None:
            return False
        try:
            started = await asyncio.to_thread(self._echo_canceller.start)
        except Exception:  # noqa: BLE001 - audio safety fallback must always run
            started = False
        if not started:
            self._half_duplex = True
            self._emit("connected", "Echo cancellation unavailable; using safe half-duplex audio.")
        return started

    async def _send_microphone(self, session: Any) -> None:
        """Forward microphone PCM to Gemini, staying quiet while Kel is speaking."""
        mute_frames = 0
        while True:
            chunk = await self._microphone.read_chunk()
            # Mute for the WHOLE turn she's speaking, not just while the playback buffer
            # happens to be non-empty. Her audio streams in bursts, so the buffer briefly
            # empties between chunks mid-sentence; keying only off is_playing() unmuted the
            # mic there, fed her own voice back in, and Gemini heard the echo as a barge-in
            # and cut her off. `_speaking` stays true across those gaps until the turn ends.
            if self._half_duplex and (self._speaking or self._speaker.is_playing()):
                mute_frames = self._mute_tail_frames
            if mute_frames > 0:
                mute_frames -= 1
                continue
            await session.send_realtime_input(
                audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={GEMINI_INPUT_RATE}")
            )
            await self._maybe_send_tone(session, chunk)

    async def _maybe_send_tone(self, session: Any, chunk: bytes) -> None:
        """Read how the user sounds and, on a notable shift, cue the model (debounced)."""
        if self._prosody is None:
            return
        if self._tone_cooldown > 0:
            self._tone_cooldown -= 1
        label = self._prosody.add(chunk)
        if not label or self._tone_cooldown > 0 or label == self._last_tone:
            return
        self._last_tone = label
        self._tone_cooldown = 150  # ~3s at 20 ms frames, so cues stay sparse
        with contextlib.suppress(Exception):
            await session.send_realtime_input(text=f"(voice tone: {label})")

    async def _receive_events(self, session: Any) -> None:
        """Receive Live server messages, re-opening the stream for every turn.

        Gemini's ``session.receive()`` yields one turn's messages and then ends, so we
        must call it again for the next turn - otherwise Kel answers once and then goes
        silent, which looks exactly like a dropped connection. A single bad message is
        logged and skipped so it can never tear down the whole conversation.
        """
        while True:
            async for message in session.receive():
                try:
                    await self._handle_message(message)
                except Exception as error:  # noqa: BLE001 - one bad message must not end the call
                    self._emit("error", f"Hiccup handling a message: {error}")

    async def _handle_message(self, message: Any) -> None:
        """Translate one Gemini Live message into playback, state, and display events."""
        # Remember the latest resumption handle so a reconnect continues this chat.
        update = message.session_resumption_update
        if update is not None and getattr(update, "new_handle", None):
            self._resume_handle = update.new_handle
        if message.go_away is not None:
            self._emit("connected", "Session is wrapping up — reconnecting shortly.")

        if message.tool_call is not None:
            await self._handle_tool_calls(message.tool_call)
            return

        content = message.server_content
        if content is not None:
            if content.interrupted:
                self._speaker.interrupt()
                self._set_speaking(False)
                self._emit("interrupted", "Kel stopped to listen.")
            if content.input_transcription and content.input_transcription.text:
                self._on_user_text(content.input_transcription.text)
            if content.output_transcription and content.output_transcription.text:
                self._begin_model_turn()
                self._assistant_buf += content.output_transcription.text

        audio = message.data
        if audio:
            self._begin_model_turn()
            if not self._type_mode:
                self._set_speaking(True)
                self._speaker.enqueue(
                    item_id=f"gemini-{self._turn_seq}", content_index=0, audio=audio
                )

        if content is not None and content.turn_complete:
            self._end_model_turn()

    def _on_user_text(self, text: str) -> None:
        """Accumulate the user's streamed transcription and barge in on first word."""
        if not self._user_turn_open:
            self._user_turn_open = True
            self._speaker.interrupt()
            self._set_speaking(False)
            self._emit("speech_started", "Listening...")
        self._user_buf += text

    def _begin_model_turn(self) -> None:
        """Finalize the user's turn the moment Kel begins responding."""
        if not self._user_turn_open:
            return
        self._user_turn_open = False
        self._turn_seq += 1
        transcript = self._user_buf.strip()
        self._user_buf = ""
        if transcript:
            self._emit("user_transcript", transcript)
            self._capture_memory(transcript)
            if self._type_mode:
                self._spawn(self._type_user_transcript(transcript))
        if self._type_mode:
            self._emit("type_mode", "Typing...")
        else:
            self._emit("speech_stopped", "Thinking...")

    def _end_model_turn(self) -> None:
        """Emit the assistant transcript and reset for the next exchange."""
        if self._user_turn_open:
            self._begin_model_turn()
        self._set_speaking(False)
        transcript = self._assistant_buf.strip()
        self._assistant_buf = ""
        if transcript and not self._type_mode:
            self._emit("assistant_transcript", transcript)

    def _set_speaking(self, speaking: bool) -> None:
        """Emit a speaking/done event only on change, for the face's lip-sync."""
        if speaking != self._speaking:
            self._speaking = speaking
            self._emit("assistant_speaking" if speaking else "assistant_done", "")

    async def _handle_tool_calls(self, tool_call: Any) -> None:
        """Run each requested tool and return its result - with any image attached."""
        responses: list[dict[str, Any]] = []
        any_image = False
        for call in tool_call.function_calls:
            args = dict(call.args or {})
            output, image = await self._run_tool(call.name, args)
            entry: dict[str, Any] = {
                "id": call.id,
                "name": call.name,
                "response": {"result": output},
            }
            if image is not None:
                # An image inside the tool response is what the model reads when it calls
                # `look` - the deterministic, intended path. Feeding it any other way (a
                # realtime video frame, or client_content) either races the reply or
                # interrupts it, so the model "can't see" or answers about nothing.
                entry["parts"] = [
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": base64.b64encode(image).decode("ascii"),
                        }
                    }
                ]
                any_image = True
            responses.append(entry)
        if self._session is None:
            return
        await self._send_tool_responses(responses, any_image)

    async def _send_tool_responses(self, responses: list[dict[str, Any]], any_image: bool) -> None:
        """Return tool results, posting the raw wire payload when an image is attached.

        The SDK's ``send_tool_response`` serializes via ``model_dump()`` without
        ``mode='json'``, so a JPEG's raw bytes never get base64-encoded and ``json.dumps``
        dies with "Object of type bytes is not JSON serializable" - dropping the link. We
        sidestep that one gap by sending the already-encoded payload over the socket; the
        plain text-only case still goes through the normal, supported method.
        """
        session = self._session
        websocket = getattr(session, "_ws", None)
        if any_image and websocket is not None:
            payload = {"toolResponse": {"functionResponses": responses}}
            await websocket.send(json.dumps(payload))
            return
        await session.send_tool_response(
            function_responses=[
                types.FunctionResponse(id=item["id"], name=item["name"], response=item["response"])
                for item in responses
            ]
        )

    async def _run_tool(self, name: str, args: dict[str, Any]) -> tuple[str, bytes | None]:
        """Execute one tool and return its text result plus an optional image."""
        if name == LOOK_TOOL_NAME:
            return await self._look()
        if name == SEE_SCREEN_TOOL_NAME:
            return await self._see_screen()
        if name == REMEMBER_TOOL_NAME:
            return await self._remember(self._arg(args, "text")), None
        if name == RECALL_TOOL_NAME:
            return await self._recall(self._arg(args, "query")), None
        if name == SET_FEELING_TOOL_NAME:
            return await self._set_feeling(self._arg(args, "feeling")), None
        if name == MOVE_TOOL_NAME:
            return await self._move(self._arg(args, "motion")), None
        if name == OPEN_URL_TOOL_NAME:
            return await self._open_url(self._arg(args, "url")), None
        if name == WEB_SEARCH_TOOL_NAME:
            return await self._web_search(self._arg(args, "query")), None
        if name == RUN_COMMAND_TOOL_NAME:
            return await self._run_command(self._arg(args, "command")), None
        if name == RUN_IN_TERMINAL_TOOL_NAME:
            return await self._run_in_terminal(self._arg(args, "command")), None
        if name == TYPE_TEXT_TOOL_NAME:
            return await self._type_text(self._arg(args, "text")), None
        if name == PRESS_KEY_TOOL_NAME:
            return await self._press_key(self._arg(args, "key")), None
        if name == START_TYPE_MODE_TOOL_NAME:
            return self._start_type_mode(), None
        if name == SWIPE_DESKTOP_TOOL_NAME:
            return await self._swipe_desktop(self._arg(args, "direction")), None
        if name == BUILD_SKILL_TOOL_NAME:
            return await self._build_skill(self._arg(args, "goal")), None
        skill = self._skills.get(name) if self._skills is not None else None
        if skill is not None and skill.enabled:
            self._emit("acted", f"Running skill: {name}")
            result = await asyncio.to_thread(run_skill, skill, args, timeout=self._skills_timeout)
            return result.output, None
        return "I don't have that tool.", None

    @staticmethod
    def _arg(args: dict[str, Any], key: str) -> str:
        return str(args.get(key, "")).strip()

    def _skill_specs(self) -> list[dict[str, Any]]:
        return self._skills.tool_specs() if self._skills is not None else []

    async def _build_skill(self, goal: str) -> str:
        if self._author is None or not goal:
            return "I can't build new skills right now."
        self._emit("acted", f"Building a skill: {goal}")
        outcome = await asyncio.to_thread(self._author.build, goal)
        return outcome.output

    async def _look(self) -> tuple[str, bytes | None]:
        """Capture one fresh camera frame to attach for the model to read."""
        try:
            if self._camera is None:
                raise CameraError("No camera is configured.")
            # Bound the capture so a slow/stuck camera can never stall the connection.
            jpeg = await asyncio.wait_for(asyncio.to_thread(self._camera.capture_jpeg), timeout=6.0)
        except Exception as error:  # noqa: BLE001 - any capture issue degrades gracefully
            self._emit("error", f"Camera unavailable: {error}")
            return f"The camera is unavailable right now ({error}).", None
        self._emit("looked", "Kel glanced at the camera.")
        return "Captured the current camera view; it is attached as an image.", jpeg

    async def _see_screen(self) -> tuple[str, bytes | None]:
        """Capture one screenshot to attach for the model to read."""
        try:
            if self._screen is None:
                raise ScreenError("No screen capture is configured.")
            jpeg = await asyncio.wait_for(asyncio.to_thread(self._screen.capture_jpeg), timeout=8.0)
        except Exception as error:  # noqa: BLE001 - any capture issue degrades gracefully
            self._emit("error", f"Screen unavailable: {error}")
            return f"I can't see the screen right now ({error}).", None
        self._emit("looked", "Kel glanced at the screen.")
        return "Captured the current screen; it is attached as an image.", jpeg

    async def _remember(self, text: str) -> str:
        if self._memory is not None and text:
            await asyncio.to_thread(self._memory.remember, text)
            self._emit("remembered", f"Remembered: {text}")
            return "Saved that to memory."
        return "I couldn't save that."

    async def _recall(self, query: str) -> str:
        memories: list[str] = []
        if self._memory is not None and query:
            memories = await asyncio.to_thread(self._memory.recall, query)
        self._emit("recalled", "Checked memory.")
        if memories:
            joined = "\n".join(f"- {memory}" for memory in memories)
            return f"Relevant things you've told me:\n{joined}"
        return "I don't have anything saved about that."

    async def _set_feeling(self, feeling: str) -> str:
        feeling = feeling or "normal"
        if self._orb is not None:
            self._orb.set_feeling(feeling)
            self._emit("acted", f"Feeling {feeling}")
            return f"Glowing {feeling}."
        if self._body is not None:
            red, green, blue = color_for(feeling)
            await asyncio.to_thread(self._body.set_color, red, green, blue)
            self._emit("acted", f"Feeling {feeling}")
            return f"Glowing {feeling}."
        return "My body isn't connected right now."

    async def _move(self, motion: str) -> str:
        motion = (motion or "nod").lower().replace(" ", "_").replace("-", "_")
        if self._body is not None:
            # A deliberate one-off gesture (nod/shake/glance). Fire it in the background so it
            # never blocks her speech, and keep the reply terse and stage-direction-style so she
            # doesn't read it aloud - the prompt also tells her never to announce movements. Her
            # everyday liveliness is separate: the Arduino carries her head by her current mood.
            pretty = motion.replace("_", " ")
            self._spawn(asyncio.to_thread(self._body.gesture, motion, self._body_servo_pin))
            self._emit("acted", f"Moving: {pretty}")
            return f"(did {pretty})"
        return "My body isn't connected right now."

    async def _open_url(self, url: str) -> str:
        if self._browser is not None and url:
            output = await asyncio.to_thread(self._browser.open_url, url)
            self._emit("acted", output)
            return output
        return "I couldn't open the browser."

    async def _web_search(self, query: str) -> str:
        if self._browser is not None and query:
            output = await asyncio.to_thread(self._browser.search, query)
            self._emit("acted", output)
            return output
        return "I couldn't run the search."

    async def _run_command(self, command: str) -> str:
        if self._shell is not None and command:
            self._emit("acted", f"Running: {command}")
            return await asyncio.to_thread(self._shell.run, command)
        return "Running commands is turned off."

    async def _run_in_terminal(self, command: str) -> str:
        if self._launcher is not None and command:
            self._emit("acted", f"Launching: {command}")
            return await asyncio.to_thread(self._launcher.launch, command)
        return "Launching is turned off."

    async def _type_text(self, text: str) -> str:
        if self._keyboard is not None and text:
            output = await asyncio.to_thread(self._keyboard.type_text, text)
            self._emit("acted", output)
            return output
        return "Typing is turned off."

    async def _press_key(self, key: str) -> str:
        if self._keyboard is not None and key:
            output = await asyncio.to_thread(self._keyboard.press_key, key)
            self._emit("acted", output)
            return output
        return "Typing is turned off."

    async def _swipe_desktop(self, direction: str) -> str:
        if self._keyboard is not None and direction:
            output = await asyncio.to_thread(self._keyboard.swipe, direction)
            self._emit("acted", output)
            return output
        return "Desktop swiping is turned off."

    def _start_type_mode(self) -> str:
        """Switch later speech turns from spoken replies to direct typing."""
        if self._keyboard is None:
            return "Typing mode is unavailable because keyboard control is turned off."
        self._type_mode = True
        self._type_mode_needs_separator = False
        self._emit("type_mode", "Typing mode on — speak to type; say 'stop typing' to exit.")
        return "Typing mode is on. Briefly confirm that later speech is typed directly."

    async def _type_user_transcript(self, transcript: str) -> None:
        """In typing mode, type the user's words (or apply a dictation command)."""
        command = parse_dictation(transcript)
        if command.stop:
            self._type_mode = False
            self._type_mode_needs_separator = False
            self._emit("type_mode", "Typing mode off — normal conversation restored.")
            return
        if self._keyboard is None:
            return
        outputs: list[str] = []
        if command.text:
            if self._type_mode_needs_separator:
                outputs.append(await asyncio.to_thread(self._keyboard.press_key, "space"))
            outputs.append(await asyncio.to_thread(self._keyboard.type_text, command.text))
            self._type_mode_needs_separator = True
        if command.press_space:
            outputs.append(await asyncio.to_thread(self._keyboard.press_key, "space"))
            self._type_mode_needs_separator = False
        if command.press_enter:
            outputs.append(await asyncio.to_thread(self._keyboard.press_key, "Return"))
            self._type_mode_needs_separator = False
        if outputs:
            self._emit("acted", " ".join(outputs))

    def _capture_memory(self, transcript: str) -> None:
        """Quietly save what the user said so Kel keeps remembering everything."""
        if self._auto_capture_memory and self._memory is not None and transcript:
            self._spawn(asyncio.to_thread(self._safe_remember, transcript))

    def _safe_remember(self, transcript: str) -> None:
        # background capture must never disrupt the chat
        with contextlib.suppress(Exception):
            self._memory.remember(transcript)  # type: ignore[union-attr]

    def _spawn(self, coro: Any) -> None:
        """Run a fire-and-forget background coroutine, tracked so it isn't GC'd."""
        task = asyncio.ensure_future(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    def _emit(self, kind: Any, text: str = "") -> None:
        self._on_event(RealtimeDisplayEvent(kind=kind, text=text))
