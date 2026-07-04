# see_screen — on-demand screen vision

## Goal

Let Kel see the user's screen on demand, the same way she sees through her camera:
a tool she calls when a question needs it, returning one fresh screenshot.

## Approach

Mirror the existing `look` tool exactly. `look` returns one JPEG from the webcam;
`see_screen` returns one JPEG of the screen (via `grim`). All the image-attachment
plumbing (tool spec → both brains → attach image → respond) already exists.

## Components

- **`src/kel/vision/screen.py`** — `GrimScreen` with `capture_jpeg() -> bytes`
  (mirrors the `Camera` protocol). Runs `grim` to grab the screen, decodes with
  cv2, downscales to `max_width`, re-encodes JPEG. The subprocess call is injected
  (`run`) so it is unit-testable with no display. `ScreenError` on failure.
- **`options.py`** — `SEE_SCREEN_TOOL_NAME = "see_screen"` + `_SEE_SCREEN_TOOL`
  spec; a `screen_enabled` flag; included in `tool_specs()` when on. Gemini picks
  it up automatically (generic `gemini_tools` conversion).
- **`gemini_session.py` + `session.py`** — a `screen` dependency and a
  `_see_screen` handler that mirrors `_look` (attach the screenshot, or degrade
  with "I can't see the screen right now (...)").
- **`settings.py`** — `KEL_SCREEN_ENABLED` (default off) and `KEL_SCREEN_MAX_WIDTH`
  (default 1280 — bigger than the webcam so on-screen text stays readable, at a
  higher token cost). Wired into `RealtimeSessionOptions` and `realtime/app.py`.
- **Prompt** — a line telling her to call `see_screen` for anything on the screen
  (errors, text, "what am I looking at"), silently, like `look`.
- **Setup** — `.env.example` + `kel-setup` gain the option.

## Design notes

- **Resolution vs cost**: screenshots need to stay legible, so the default width
  is larger than the camera's 768. Configurable.
- **Platform**: `grim` is Wayland/wlroots (the owner's Niri). Missing/failed grim
  degrades cleanly — she says she can't see the screen. X11 users would need a
  different capture tool (future).
- **Both brains**: the tool spec is shared, so both the Gemini and OpenAI sessions
  get a `_see_screen` handler to stay in parity.

## Tests

- `GrimScreen` with an injected runner: returns JPEG, downscales wide captures,
  raises `ScreenError` on empty/failed capture.
- Session `_see_screen`: attaches an image when a screen is present; degrades to a
  clear message when it is not.
- `tool_specs()` exposes `see_screen` only when `screen_enabled`.

## Out of scope

Continuous/realtime screen streaming (a possible later "watch mode").
