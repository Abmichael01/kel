# Kel architecture

## The main idea

The robot is split into two layers:

```text
Human
  |
  v
Computer or Raspberry Pi
  microphone -> Python -> AI -> Python -> speaker
                         |
                         v
                  validated command
                         |
                         v
                      Arduino
                motors, LEDs, sensors
```

Python is the brain and Arduino is the body controller. The Arduino does not run
the language model. It performs small deterministic actions and reports sensor
data. This keeps the system easier to understand and much safer.

## Why Python

Python works on both the development computer and Raspberry Pi. It has mature
libraries for OpenAI, audio, serial communication, cameras, and robotics. The
Arduino will use its normal C++-based sketch language because it is designed for
precise hardware control.

## Current request flow

The original text milestone follows this path:

```text
Terminal UI
    -> ConversationSession
        -> ChatGateway contract
            -> OpenAIChat implementation
                -> OpenAI Responses API
```

The return journey carries two values:

- `text`: the answer displayed to the user.
- `response_id`: the identifier used to continue the same conversation.

`ConversationSession` remembers only that identifier. It does not know anything
about HTTP, OpenAI SDK objects, microphones, or Arduino ports.

## Responsibilities

### Configuration

`config/settings.py` loads environment variables and rejects missing required
values early. Secret values never belong in source code.

### Prompts

`prompts/kel_personality.py` contains Kel's behavioral instructions. Keeping the
prompt in code gives it normal review and test coverage. The prompt is sent on
every request because API-level instructions apply only to the current response.

### AI provider

`ai/gateway.py` defines the small contract the application needs: accept a user
message and return an answer. `ai/openai_chat.py` is the only module that knows
the OpenAI SDK.

### Conversation

`conversation/session.py` owns multi-turn state. Because it depends on the
gateway contract instead of OpenAI directly, tests can use a fake provider and
future AI providers can be added without changing the session.

### Interface

`interfaces/cli.py` owns typed terminal input and output.
`interfaces/voice_cli.py` owns push-to-talk prompts. Microphone code remains in
the voice package rather than being mixed into either interface or the AI code.

### Application wiring

`app.py` creates the typed-chat objects. `voice/app.py` constructs voice-only
dependencies. Keeping construction at these boundaries makes dependencies
visible and prevents modules from secretly creating each other.

### Computer actions

`system/` contains the operating-system adapters that open browser pages, run
short shell commands, launch long-running commands in a separate terminal, and
type into the field the user has focused. It also maps spoken left/right swipes
to Niri's native column-navigation actions, with fixed `Super+Left` and
`Super+Right` shortcuts as the fallback on other desktops. Realtime conversation
logic calls these adapters through injected objects; it does not depend on
subprocess or desktop-tool details.

Continuous typing mode remains inside the Realtime boundary. The model only starts
the mode; after that, `realtime/dictation.py` converts completed transcripts into
text plus the allowlisted Enter/exit controls. The session temporarily disables
automatic model responses, avoids saving dictated content to memory, and sends
text through the keyboard adapter until the user exits the mode.

Browser opening is enabled separately because it is lower risk. Shell, terminal,
and keyboard actions share the explicit `KEL_SHELL_ENABLED` opt-in. Keyboard text
is passed as a subprocess argument rather than through a shell, and the user must
choose the destination by focusing a field first. See `docs/system.md` for setup
and the remaining risks of model-selected computer actions.

## Current voice boundary

The first voice milestone is a chained push-to-talk workflow:

```text
microphone.py
    -> openai_transcriber.py
        -> existing ConversationSession
            -> openai_speech.py
                -> speaker.py
```

`voice/contracts.py` defines the small data types and interfaces shared by those
stages. `voice/workflow.py` runs transcription, conversation, and speech
generation in order. `interfaces/voice_cli.py` owns only the terminal prompts
that start and stop microphone capture.

Push-to-talk was chosen because every stage is visible and independently
testable. It also reuses the existing conversation state and remains available
as a diagnostic fallback.

## Current Realtime boundary

The low-latency path is a separate speech-to-speech architecture:

```text
StreamingMicrophone
    -> persistent Realtime WebSocket
        -> streaming model audio deltas
            -> PcmPlaybackBuffer
                -> StreamingSpeaker
```

`realtime/options.py` owns the API session schema. `realtime/audio.py` owns local
PCM capture, buffering, and playback. `realtime/session.py` owns the WebSocket
event loop and interruption state. `interfaces/realtime_cli.py` only renders
human-readable status and transcripts.

`realtime/echo_cancel.py` owns the optional PipeWire WebRTC echo-cancellation
route. It creates temporary virtual input/output nodes before audio streams open
and restores the previous defaults afterward. Failure degrades to half-duplex, so
speaker echo cannot become an uncontrolled conversation loop.

Audio is sent while the user is still talking. Server VAD commits the turn after a
short silence but does not automatically start inference. The session waits for
the completed transcript, retrieves relevant vector memories, supplies them as
per-response instructions, then creates the response. Output audio is played as
chunks arrive rather than waiting for a complete file.

When a user speaks during Kel's answer, the local buffer discards audio that was
not played. The session reports how many milliseconds were actually heard and
truncates the assistant conversation item at that position. This prevents future
responses from assuming the user heard words that were interrupted.

## Planned Arduino boundary

Python and Arduino will communicate over USB serial. They will exchange newline-
delimited JSON rather than unstructured sentences. A future command may look
like this:

```json
{"command":"turn_head","angle_degrees":20,"request_id":"abc123"}
```

Arduino will validate supported commands and limits, execute the action, then
return an acknowledgement:

```json
{"request_id":"abc123","status":"completed"}
```

The AI will never write directly to pins or invent raw motor values. A hardware
service will translate allowlisted actions, clamp safe limits, enforce timeouts,
and stop motion if communication is lost.

## Milestones

1. Text chat on the computer. **Complete.**
2. Push-to-talk microphone and speaker flow. **Complete.**
3. Natural realtime voice conversation. **Complete.**
4. Simulated allowlisted robot actions.
5. USB serial connection to an Arduino.
6. Sensors, servos, motors, and emergency-stop behavior.
7. Move the Python brain from the computer to Raspberry Pi.
