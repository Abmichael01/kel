# Share Kel — install UX & graceful degradation

## Goal

Let another person (a Linux friend, similar setup) install and run Kel with a
smooth first-run experience, and have her run cleanly even when hardware
(Arduino, camera) and optional services (OpenAI) are absent.

## Problems this fixes

1. `OPENAI_API_KEY` is **hard-required** at startup (`settings.py`), so a
   Gemini-only user cannot start Kel at all without a second, paid key they do
   not use for her brain.
2. `.env.example` only contains the 3 body settings — a new user copying it gets
   a broken config with none of the keys or options.
3. The wake-word model lives under gitignored `models/`, so a fresh clone has no
   model and wake word silently breaks.
4. No guided setup — only manual README steps.
5. Shared installs would inherit unsafe defaults (unrestricted shell on).

Already handled (verify only): a missing Arduino body and a missing on-screen
face already degrade gracefully (`realtime/app.py`, `wake/app.py`).

## Design

### 1. `kel-setup` interactive wizard

New package `src/kel/setup/` with a **pure logic core** (testable, no I/O) and a
thin prompt shell.

- `wizard.py` — `build_env_text(answers) -> str` (pure): renders a complete
  `.env` from an `Answers` dataclass. No prompts, no filesystem.
- `cli.py` — `main()`: gathers answers via prompts, lists audio devices, offers
  the wake-model download, auto-detects Arduino + camera, writes `.env`, prints
  the "you're ready" message. Entry point `kel-setup`.

Flow: welcome/deps → Gemini key (required, with free-key link) → OpenAI key
(optional, "only for memory + chained voice; Enter to skip") → audio devices →
wake model (download or skip) → hardware auto-detect → safety (shell off by
default, opt-in) → write `.env` → done.

Safety default: `KEL_SHELL_ENABLED=false` for shared installs (tripwire on),
`KEL_BROWSER_ENABLED=true`. The owner's own gitignored `.env` is untouched.

### 2. Gemini-only start actually works

`settings.py`: OpenAI key becomes **provider-aware**. Required only when
`KEL_REALTIME_PROVIDER=openai`; optional when `gemini`. The placeholder
`replace-with-your-api-key` counts as empty.

Feature gating when no OpenAI key:
- Long-term memory (uses `OpenAIEmbedder`) is skipped with a clear note —
  `realtime/app.py` builds memory only when `memory_enabled` **and** a key is
  present.
- Text chat (`kel`) and chained voice (`kel-voice`) give a clean "needs an
  OpenAI key" error instead of a raw auth failure.

### 3. Complete `.env.example`

Full, commented template, placeholders only (never a real key), with the safe
sharing defaults above.

### 4. Harden graceful degradation

Verify + fill gaps so a minimal setup (Gemini key only; no Arduino, camera, wake
model, or OpenAI) runs clean and states what is off and why:
- missing wake model → wake disabled with a friendly note,
- missing camera → vision degrades (already guarded at call time),
- memory off → no crash, no memory tools.

### 5. Tests + docs

- Unit tests for `build_env_text` (skip paths: no OpenAI key, no wake, no body).
- A settings test proving a Gemini-only config (no OpenAI key) builds.
- README "Share Kel" quick-start pointing at `kel-setup`.

All tests use fakes — no real prompts, network, or audio.

## Out of scope (future)

- Moving memory embeddings to Gemini to drop the second key entirely.
- Mac/Windows support for the Linux-only system tools.
