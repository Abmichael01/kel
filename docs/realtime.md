# Kel Realtime voice guide

## Why this mode is faster

The push-to-talk pipeline waits for three separate remote jobs: transcription,
text reasoning, and speech generation. It also waits for complete recordings and
complete generated WAV files.

Realtime mode keeps one WebSocket connection open and streams in both
directions:

```text
microphone PCM -> WebSocket -> Realtime model -> PCM deltas -> speaker buffer
```

The server receives audio while you are speaking. When it detects the end of the
turn, Kel waits for the completed transcript, retrieves relevant long-term memory,
then manually starts the model response. Kel plays the first returned audio chunks
without waiting for the full response.

## Run it

```bash
uv sync --extra dev --extra voice
uv run kel-realtime
```

There is no record button. Speak naturally after `Live connection ready`
appears. Pause when finished, then Kel answers. Speak again to interrupt. Press
`Ctrl+C` to close the microphone, speaker, and WebSocket cleanly.

This computer uses PipeWire's WebRTC echo canceller and sets
`KEL_REALTIME_HALF_DUPLEX=false`, so microphone audio continues flowing while Kel
speaks and you can interrupt mid-sentence without feeding Kel's speaker audio back
as user speech:

```text
KEL_AUDIO_INPUT_DEVICE=pulse
KEL_AUDIO_OUTPUT_DEVICE=pulse
KEL_REALTIME_ECHO_CANCEL=true
KEL_REALTIME_HALF_DUPLEX=false
```

At session startup, Kel creates temporary `kel_echo_cancel_source` and
`kel_echo_cancel_sink` nodes, makes them the Pulse/PipeWire defaults, then restores
the previous defaults when the session closes. If AEC cannot start, Kel
automatically falls back to half-duplex rather than risking a feedback loop.
Headphones remain the most reliable option in a very loud room.

## Module responsibilities

### `realtime/options.py`

Creates the session configuration: model, voice, 24 kHz PCM formats, input
transcription, noise reduction, output limits, and turn detection.

### `realtime/audio.py`

`StreamingMicrophone` captures one-channel signed 16-bit PCM in 20 ms blocks.
The async session sends those blocks without constructing a WAV file.

`PcmPlaybackBuffer` receives model audio deltas from the network thread and feeds
the sounddevice callback. The buffer also measures how much of the current answer
was handed to the speaker.

`StreamingSpeaker` requests 20 ms of sound at a time. If the network has not
provided speech yet, it outputs silence rather than blocking the audio thread.

### `realtime/echo_cancel.py`

Temporarily routes the microphone and speaker through PipeWire's WebRTC AEC nodes.
This concern stays outside PCM buffering and restores the user's previous audio
defaults on shutdown.

### `realtime/session.py`

Maintains the persistent OpenAI connection and reacts to typed server events:

- `input_audio_buffer.speech_started`: the user began talking.
- `input_audio_buffer.speech_stopped`: the user's turn ended.
- `response.output_audio.delta`: another chunk is ready for playback.
- `response.output_audio_transcript.done`: Kel's spoken transcript is complete.
- `error`: a recoverable or terminal server problem occurred.

It also owns the typing-mode state switch. The model calls `start_type_mode` once;
the session then keeps VAD and transcription active while disabling automatic AI
responses. Completed transcripts go directly to the keyboard adapter until the
local parser hears `stop typing` or another exit phrase.

### `interfaces/realtime_cli.py`

Prints connection state, listening/thinking markers, transcripts, errors, and the
AI-voice disclosure. It does not know about Base64, PCM, WebSockets, or buffers.

## Automatic turn detection

Kel currently uses server VAD. It identifies speech by audio activity and ends a
turn after 450 ms of silence. This is a compromise: shorter silence feels faster
but may cut off a thoughtful pause; longer silence feels patient but slower.

Tune these values in `.env`:

```text
KEL_REALTIME_VAD_THRESHOLD=0.5
KEL_REALTIME_VAD_SILENCE_MS=450
```

Raise the threshold if background noise triggers Kel. Lower it if quiet speech
is missed. Try `350` ms silence for a snappier conversation or `600` ms if Kel
interrupts pauses too eagerly.

Automatic response creation stays disabled so the application can retrieve memory
after transcription and before inference. Response interruption stays enabled in
normal conversation. Typing mode temporarily disables interruption too, keeping
speech chunking and transcription alive without a model response; leaving typing
mode restores normal interruption.

## Microphone noise reduction

The default is suitable for a laptop or room microphone:

```text
KEL_REALTIME_NOISE_REDUCTION=far_field
```

Use `near_field` for a headset or close-talking microphone.

## Model choice

The default is:

```text
KEL_REALTIME_MODEL=gpt-realtime-mini
```

It is useful while tuning because it supports direct realtime audio and is the
cost-efficient Realtime model. Later, set `gpt-realtime-1.5` to compare flagship
voice quality, or evaluate `gpt-realtime-2` when Kel needs more complex tool use.

## Interruption process

When new user speech starts during playback:

1. Server VAD cancels the model response because `interrupt_response` is enabled.
2. The local PCM buffer immediately drops chunks that have not played.
3. Kel calculates the playback position in milliseconds.
4. A conversation truncation event removes the unheard tail of the answer from
   model context.

This detail matters for a robot. If Kel said five instructions but the user only
heard two before interrupting, the next turn should not assume all five were
heard.

## Known boundaries

- Network latency still affects responsiveness.
- Realtime audio costs differ from the chained text pipeline.
- Kel deliberately waits for input transcription and memory retrieval before
  starting each normal response, adding a little latency for reliable recall.
- Sessions have a platform duration limit. Restart the command if a long-running
  development session closes.
- Arduino tools are not connected yet. Realtime function calls will eventually
  enter the same validated command layer planned for hardware safety.
