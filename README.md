# Kel

Kel is a conversational robot project. Kel currently supports typed chat,
inspectable push-to-talk voice, and low-latency realtime speech on a computer.
Raspberry Pi deployment and Arduino control are the next major stages.

## What works now

- A terminal conversation with Kel.
- A push-to-talk microphone conversation with an AI-generated spoken reply.
- A continuous Realtime conversation with automatic turn detection and
  interruption, protected from speaker feedback by PipeWire WebRTC echo cancellation.
- Multi-turn context using OpenAI's Responses API.
- Automatic vector-memory recall before every normal Realtime response.
- Optional browser, terminal, and focused-field typing actions in Realtime mode.
- Continuous voice-to-keyboard typing mode with spoken Enter and exit controls.
- Kel's personality stored as a version-controlled prompt.
- Clear module boundaries so voice and hardware can be added without rewriting
  the conversation core.
- Unit tests that run without an API key or network request.

## Requirements

- `uv` for Python environment and dependency management.
- An OpenAI API key with API billing or credits enabled.
- A microphone and speaker recognized by the operating system.
- PortAudio, which is already installed on this development computer.

The project supports Python 3.11 or newer. This computer is configured to use
Python 3.13 for the project.

## First-time setup

1. Install the project. `voice` is her brain/audio, `face` is the on-screen face,
   `robot` is the Arduino body (add `dev` if you'll run the tests):

   ```bash
   uv sync --extra voice --extra face --extra robot
   ```

2. Run the setup wizard. It asks for your (free) Gemini key, picks your audio,
   can download the wake model, detects an Arduino, and writes your `.env`:

   ```bash
   uv run kel-setup
   ```

   Prefer to do it by hand? Copy `.env.example` to `.env` and fill it in. `.env`
   is gitignored — never commit or share it. Kel runs on a **free Google Gemini
   key alone**; an OpenAI key is optional (only long-term memory and the
   push-to-talk mode use it).

3. Start talking to her:

   ```bash
   uv run kel-realtime
   ```

   `uv run kel` is a typed-chat mode instead (that one needs an OpenAI key).

## Sharing Kel with someone

She's built to run on a fresh machine gracefully: with no Arduino she still
talks (the body is optional), with no camera she just can't see, and with no
OpenAI key she runs on Gemini alone (long-term memory turns off until a key is
added). Hand a friend the repo, have them run `uv run kel-setup`, and she's
ready. The wizard defaults to safe settings — computer/shell control is **off**
until they explicitly turn it on. Everything below is Linux-oriented (audio,
`wtype` typing, Niri desktop actions, serial ports).

## Start voice mode

For the natural, low-latency mode, run:

```bash
uv run kel-realtime
```

The connection stays open: simply speak, wait briefly after finishing, and Kel
will answer as audio arrives. You can interrupt Kel by speaking again. Press
`Ctrl+C` to stop. Use headphones so Kel does not hear his own speaker output.

The older chained mode remains useful when debugging individual stages:

```bash
uv run kel-voice
```

Then:

1. Press Enter to begin recording.
2. Speak into the microphone.
3. Press Enter again to stop recording.
4. Read the transcript and Kel's response while the generated voice plays.

Use `/reset` to clear the conversation or `/exit` to stop. Headphones help avoid
Kel's speaker output feeding back into the microphone.

If the wrong microphone or speaker is selected, list available devices:

```bash
uv run python -m sounddevice
```

Set `KEL_AUDIO_INPUT_DEVICE` or `KEL_AUDIO_OUTPUT_DEVICE` in `.env` to a device
name or number from that list. Leave them blank to use the system defaults.

## What happens when you send a message

1. `interfaces/cli.py` reads text from the terminal.
2. `conversation/session.py` validates the message and remembers the previous
   OpenAI response ID.
3. `ai/openai_chat.py` sends the message, Kel's instructions, and conversation
   state to the OpenAI Responses API.
4. The API returns Kel's answer and a new response ID.
5. The session stores that ID and the terminal prints the answer.

This separation mattered when voice was added: the new interface reused the AI
and conversation modules without changing their responsibilities.

## What happens during a voice turn

1. `voice/microphone.py` captures 16-bit microphone samples and creates a WAV.
2. `voice/openai_transcriber.py` turns that recording into text.
3. The existing `ConversationSession` sends the text to Kel's AI brain.
4. `voice/openai_speech.py` turns Kel's text answer into an AI-generated WAV.
5. `voice/speaker.py` plays that WAV through the computer speaker.

Every intermediate result remains visible, which makes this first voice version
easier to learn and debug. See [the voice guide](docs/voice.md) for details.

## What happens during a realtime turn

1. The microphone continuously produces small 24 kHz PCM chunks.
2. `realtime/session.py` sends each chunk over one persistent WebSocket.
3. Server voice-activity detection decides when you started and stopped talking.
4. The Realtime model responds directly with incremental PCM audio chunks.
5. `realtime/audio.py` places each chunk into the speaker buffer immediately.
6. If you speak during playback, unplayed audio is cleared and the unheard part
   of Kel's answer is removed from conversation state.

See [the Realtime guide](docs/realtime.md) for the complete process and tuning
controls. See [the computer actions guide](docs/system.md) to let Kel open pages,
run commands, or type into a field you focus.

## Project map

```text
.
├── AGENTS.md                  # Durable guidance for future AI coding agents
├── docs/
│   ├── architecture.md        # Detailed design and roadmap
│   ├── realtime.md            # Low-latency streaming and interruption
│   ├── system.md              # Browser, terminal, and focused-field actions
│   └── voice.md               # Push-to-talk flow and troubleshooting
├── src/kel/
│   ├── ai/                    # AI contract and OpenAI implementation
│   ├── config/                # Environment-based settings
│   ├── conversation/          # Provider-independent session logic
│   ├── interfaces/            # Typed and voice terminal interfaces
│   ├── prompts/               # Kel's personality and behavioral rules
│   ├── realtime/              # WebSocket session and full-duplex PCM audio
│   ├── system/                # Browser, shell, terminal, and keyboard adapters
│   ├── voice/                 # Recording, transcription, speech, and playback
│   └── app.py                 # Connects the typed-chat modules
└── tests/                     # Offline unit tests
```

## Development checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

See [the architecture guide](docs/architecture.md) for the full design and the
planned Arduino communication flow.
