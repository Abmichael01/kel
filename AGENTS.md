# Kel project guidance

## Product intent

Kel is a conversational robot. During the first phase, Kel runs on a computer as
a text and voice assistant. Later, the same Python application will run on a
Raspberry Pi and exchange safe, structured commands with an Arduino.

## Working agreement with the owner

- Teach while building. Explain each important process in plain language and
  keep the documentation aligned with the code.
- Prefer small, understandable steps that can be run and verified before the
  next feature is added.
- Keep code modular. A module should have one clear responsibility.
- Group related code together, but do not place unrelated concerns in the same
  file or folder simply because it is convenient.
- Keep user interfaces, AI providers, conversation logic, voice I/O, and
  hardware communication separate.
- When an architectural decision changes, update `docs/architecture.md`.
- When setup or commands change, update `README.md`.

## Current module boundaries

- `config/`: environment variables and application settings only.
- `ai/`: provider interfaces and OpenAI API implementation only.
- `conversation/`: provider-independent conversation state and orchestration.
- `prompts/`: version-controlled instructions that shape Kel's behavior.
- `interfaces/`: ways a human interacts with Kel, beginning with the terminal.
- `voice/`: microphone and speaker concerns when voice is introduced.
- `realtime/`: continuous PCM streaming, Realtime API state, and interruption
  handling. Keep it independent from the chained `voice/` fallback.
- `hardware/`: validated robot commands and Arduino transport when hardware is
  introduced.

Do not make conversation logic import the terminal UI. Do not make domain logic
depend directly on Arduino, audio, or OpenAI SDK details. Wire implementations
together at the application boundary.

## Robot safety rules

- Never send arbitrary model-generated text directly to motors or actuators.
- Convert requested actions to a small allowlisted command schema, validate
  limits, and require hardware acknowledgements.
- Physical motion must eventually have timeouts, an emergency stop, and a safe
  default state when communication is lost.
- Kel must not claim a physical action happened until the hardware confirms it.

## Secrets

- Never commit `.env` or an API key.
- Keep `OPENAI_API_KEY` in the local environment or local `.env` file.
- Examples must use placeholders, never real credentials.

## Verification

After Python changes, run:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tests must not call the live OpenAI API. Use fakes at the `ChatGateway` boundary.
Voice tests must also fake transcription and speech generation. A live voice
smoke test may be run manually when the owner explicitly asks to test voice.
