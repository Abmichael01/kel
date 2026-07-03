# Kel attention gate (wake / sleep word) — design

**Date:** 2026-06-28
**Status:** Approved for planning
**Scope:** Realtime voice mode (`kel-realtime`) only, this milestone.

## Problem

Kel's realtime mode connects the microphone straight to the OpenAI Realtime
WebSocket and responds to whatever it hears. If left always-on it would react to
the TV, other people, coughs, and background noise — and every one of those
sounds would be streamed to the cloud (cost and privacy). Kel needs to know
**when it is actually being talked to**.

## Solution summary

Put a tiny, always-on, fully local **wake-word detector** in front of the
realtime pipeline as an *attention gate*. The detector listens continuously on
the local machine and sends nothing anywhere. Only the two trigger phrases
change Kel's state:

- **"kel pay attention"** → wake (ASLEEP → AWAKE)
- **"kel at ease"** → sleep (AWAKE → ASLEEP)

While ASLEEP, only the detector runs — the Realtime WebSocket is not even
connected, so Kel cannot react to anything and incurs no cloud cost. While
AWAKE, the existing realtime pipeline runs as a normal free-flowing
conversation. Nothing inside the `realtime/` package changes; the gate only
decides *when a realtime session is allowed to exist*.

This is a **latched gate** (one phrase opens, another closes), not a
per-utterance wake word.

## Confirmed decisions

| Decision | Choice |
| --- | --- |
| Detection engine | **Porcupine** (Picovoice), hidden behind a `WakeWordDetector` interface so openWakeWord can replace it in one file later |
| Mode covered now | **Realtime only** (`kel-realtime`); push-to-talk is future work |
| Behavior while AWAKE | **Full conversation** — respond to everything until sleep, no need to repeat the name |
| Auto-sleep | **Yes**, after ~90s with no user speech (tunable via `.env`) |
| Wake/sleep feedback | **Spoken acknowledgement** — "I'm listening" on wake, "Standing by" on sleep |

## User experience

```
$ uv run kel-realtime
Kel realtime voice mode
Disclosure: Kel's voice is AI-generated, not human.
Use headphones to prevent speaker echo. Press Ctrl+C to stop.
[Asleep] Say "Kel, pay attention" to wake me.

  (user) "Kel, pay attention"
Kel: I'm listening.
[Awake] Listening...
  (user) "What's the weather like for a walk?"
Kel: ...
  ... free-flowing conversation ...
  (user) "Kel, at ease"
Kel: Standing by.
[Asleep] Say "Kel, pay attention" to wake me.
```

If the user walks away mid-conversation, after ~90s of silence Kel says
"Standing by" on its own and returns to ASLEEP.

## Architecture

### State machine

```
            "kel pay attention"
   ┌──────────────────────────────────▶ AWAKE
ASLEEP                                    │
   ▲                                      │ realtime session live
   │   "kel at ease"  OR  90s no speech   │ detector still listening
   └──────────────────────────────────────┘
```

- **ASLEEP**: detector stream open; Realtime WebSocket closed. The only meaningful
  event is the `pay attention` phrase. An `at ease` phrase heard here is ignored.
- **AWAKE**: detector stream still open *and* a live `RealtimeVoiceSession`
  running. The meaningful events are the `at ease` phrase and the idle timeout.
  A second `pay attention` heard here is a no-op.

Connecting only while AWAKE also sidesteps the Realtime platform session-length
limit noted in `docs/realtime.md`: short conversations never hit it, and a new
WebSocket is created fresh on each wake.

### New package: `src/kel/wake/`

Mirrors the existing clean-boundary style (each module has one job and a narrow
interface; SDK knowledge isolated to a single adapter).

| Module | Responsibility | External knowledge |
| --- | --- | --- |
| `wake/contracts.py` | `WakeWordDetector` protocol, `Phrase` enum (`PAY_ATTENTION`, `AT_EASE`), `AttentionState` enum (`ASLEEP`, `AWAKE`), `WakeEvent` dataclass | none |
| `wake/porcupine_detector.py` | The only module importing `pvporcupine`; owns its own 16 kHz `sd.RawInputStream`; converts detected keyword index → `WakeEvent` via a callback | Picovoice SDK, sounddevice |
| `wake/gate.py` | The `AttentionGate` state machine + idle timer; pure logic; invokes `on_wake` / `on_sleep` callbacks; ignores phrases irrelevant to the current state | none (testable with a fake detector + injected clock) |
| `wake/announcer.py` | `SpokenAnnouncer` that speaks "I'm listening" / "Standing by"; renders both clips once at startup and replays cached WAV bytes for instant feedback | reuses `OpenAISpeechGenerator` + `SoundDeviceSpeaker` |
| `wake/app.py` | Builds the detector, gate, announcer, and a realtime-session *factory*; wires them into one async orchestration loop | construction only |

### Orchestration loop (replaces the body of `run_realtime`)

```text
build detector (16 kHz local stream), gate, announcer, session factory
start detector  ──WakeEvent──▶  gate
                                  │
   gate.on_wake:                  │   gate.on_sleep:
     announcer.greet()            │     cancel realtime task
     start RealtimeVoiceSession   │     announcer.farewell()
       as an asyncio task         │     reset idle timer
     wire session on_event ───────┘
       so speech_started resets the idle timer
```

- The detector runs for the entire process lifetime (both states).
- On wake: announce, then create a **new** `RealtimeVoiceSession` via
  `build_realtime_session(...)` and run `session.run()` as a cancellable task.
- The session's `on_event` callback is wrapped so that `speech_started` events
  reset the gate's 90s idle timer (and still forward to the terminal display).
- On sleep (phrase or timeout): cancel the realtime task (clean teardown already
  stops mic/speaker in `RealtimeVoiceSession.run`'s `finally`), then announce.
- `Ctrl+C` cancels everything and closes the detector stream cleanly.

### Why a separate microphone stream for the detector

Porcupine requires **16 kHz** mono frames of exactly `porcupine.frame_length`
samples; the realtime path captures **24 kHz** (`REALTIME_SAMPLE_RATE`). Rather
than resample, the detector opens its **own** dedicated 16 kHz `RawInputStream`
on the same input device and keeps full ownership of it. Two input streams on
one device is supported on Linux/PulseAudio. This keeps the detector's audio
concern fully separate from the realtime audio concern.

## Configuration (added to `config/settings.py` and the private local `.env`)

| Env var | Default | Meaning |
| --- | --- | --- |
| `KEL_WAKE_ENABLED` | `true` | When false, `kel-realtime` behaves exactly as today (no gate) |
| `KEL_WAKE_ACCESS_KEY` | _(required when enabled)_ | Picovoice access key — **secret**, lives in `.env` only |
| `KEL_WAKE_KEYWORD_ATTENTION_PATH` | _(required)_ | Path to the "kel pay attention" `.ppn` file |
| `KEL_WAKE_KEYWORD_AT_EASE_PATH` | _(required)_ | Path to the "kel at ease" `.ppn` file |
| `KEL_WAKE_SENSITIVITY` | `0.5` | Porcupine sensitivity 0–1; higher = more triggers / more false positives |
| `KEL_WAKE_AUTO_SLEEP_SECONDS` | `90` | Seconds of no user speech before auto-sleep; `0` disables auto-sleep |
| `KEL_WAKE_GREETING` | `I'm listening.` | Spoken on wake |
| `KEL_WAKE_FAREWELL` | `Standing by.` | Spoken on sleep |

Validation is split for safety. `Settings.from_mapping` validates only
**formats** (the enabled flag parses as a bool, sensitivity is 0–1, auto-sleep
seconds ≥ 0), because `Settings` is shared by text chat and push-to-talk, which
must still start without any Picovoice setup. The **presence** check (enabled
requires an access key and both keyword paths) lives in
`wake/app.validate_wake_settings`, called only on the realtime path, so a missing
key stops `kel-realtime` at startup with a clear, actionable message rather than
breaking the other entrypoints.

## One-time user setup (documented in a new `docs/wake.md`)

1. Create a free Picovoice account and copy the **access key** into
   `KEL_WAKE_ACCESS_KEY`.
2. In the Picovoice Console, create two custom wake phrases — "kel pay attention"
   and "kel at ease" — for the **Linux** platform.
3. Download the two `.ppn` files and point the two keyword-path env vars at them.
4. `uv sync --extra dev --extra voice` (Porcupine is added to the `voice` extra).

## Error handling and edge cases

- **Echo / self-trigger (key risk):** while AWAKE, Kel's speaker could utter
  words close to "at ease" and false-sleep. Mitigations: (a) the existing
  headphones recommendation, (b) **suppress `at ease` detection while Kel is
  actively playing audio** — the orchestrator knows when a realtime response is
  playing and gates the sleep phrase accordingly. Documented as a known boundary.
- **False wake:** sensitivity is tunable; default 0.5. Spoken "I'm listening"
  gives immediate feedback so an accidental wake is obvious and easily undone
  with "at ease".
- **Missing/invalid Porcupine setup:** caught at startup by settings validation,
  not mid-conversation.
- **Detector device busy / unavailable:** surfaced as a clear startup error
  through the same display path used for other realtime errors.
- **Auto-sleep during Kel's turn:** the idle timer measures *user* speech
  (`speech_started`); it does not auto-sleep while Kel is mid-response.

## Testing strategy (mirrors existing `tests/` style)

- `tests/test_attention_gate.py` — the state machine with a **fake detector** and
  an **injected clock**: wake transitions, sleep on phrase, sleep on timeout,
  idle-timer reset on speech, ignoring `at ease` while ASLEEP and `pay attention`
  while AWAKE, auto-sleep disabled when seconds = 0.
- `tests/test_porcupine_detector.py` — adapter logic against a **fake
  pvporcupine** (keyword index → `Phrase` mapping, frame handling), no real audio.
- `tests/test_announcer.py` — clips rendered once and cached; replays cached
  bytes; uses a fake speech generator + fake speaker.
- `tests/test_settings.py` — extend with the new wake settings (validation,
  defaults, disabled path).

No test opens a real microphone, network, or Picovoice service.

## Dependencies

- Add `pvporcupine` to the `voice` optional-dependency group in `pyproject.toml`.

## Out of scope (future work)

- **Push-to-talk (`kel-voice`) gating** — the gate is built mode-agnostic enough
  to wrap it later, but not wired this milestone.
- **openWakeWord backend** — the `WakeWordDetector` interface exists so this is a
  later drop-in (no account, fully offline) if Porcupine's free-tier custom-model
  licensing becomes inconvenient.
- **Visual/LED feedback** — relevant once Kel reaches the Arduino/robot
  milestones; spoken feedback only for now.
- **Acoustic echo cancellation** — still deferred per `docs/realtime.md`.
```
