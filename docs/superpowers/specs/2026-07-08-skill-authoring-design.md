# Skill authoring design — Kel builds her own skills

**Date:** 2026-07-08
**Status:** Approved for planning
**Sub-project:** #2 of the "Kel grows her own skills" roadmap
**Builds on:** #1 the skill runtime (`kel.skills`: `SkillStore`, `runner`, `executor`)

## The goal (in the user's words)

> "Once I ask it to do something it takes on making the stuff — like it can code
> anything just to make sure what I said works. Its goal is to achieve what I ask
> without asking much questions."

Kel should be a **doer**. When she's asked for something she can't already do, she
writes the code to do it, tests it until it works, and does it — deciding things
herself instead of interrogating the user. #1 made hand-written skills real and
callable. #2 makes Kel **write them herself, on the fly, to fulfil a request.**

## Decisions locked (from brainstorming)

- **Full autonomy.** A skill Kel writes to fulfil a live request is built,
  self-tested, **auto-armed**, and used in one flow — no approval stop. This
  overrides #1's review-then-arm *for self-authored skills*. The arm/disarm gate
  still exists so the user can disable a skill afterward (and the #3 panel will
  use it); it is simply not a blocking step in the autonomous flow.
- **Gemini writes the code.** The coding model is Gemini (free tier, strong at
  code), via the existing `google-genai` dependency + `GEMINI_API_KEY`.
  Configurable via `KEL_CODER_MODEL`.
- **Decisive personality.** A prompt change so Kel makes sensible assumptions and
  acts instead of over-asking, and reaches for `build_skill` on her own.
- **Runs her own code automatically.** Honest note: this means Kel writes code and
  runs it on the machine with no approval step. The user chose this (Full
  autonomy); it is consistent with the unrestricted shell she already has. The
  subprocess isolation from #1 is for **stability, not security**.

## The flow

```text
You: "make me a QR code for my wifi password hunter2"
  Kel (voice): "give me a sec, putting that together"
     -> calls build_skill("generate a QR code PNG for the text 'hunter2' and save it")
         -> author loop (in the app, NOT the voice model):
             1. Gemini writes skill.py + skill.json + the args for THIS request
             2. run it in the #1 sandbox with those args
             3. failed? feed the traceback back to Gemini -> new version -> retry
                (pip-install any imports it needs), up to N attempts
             4. worked? promote into ~/.kel/skills/<name>/ ARMED (enabled: true)
         -> the successful test run IS the real run, so its output is the result
  Kel (voice): "done — saved the QR code to ~/wifi.png"
```

The key simplification: **the final successful test run uses the real args for
this request, so testing the skill *is* doing the task.** `build_skill` returns
that output, and Kel relays it. The skill is also left armed for future direct
calls. This means the immediate result works the same on both brains without
depending on #1's live tool-injection (which only the OpenAI path has).

## Goals

- A new `build_skill(goal)` tool Kel calls herself when she lacks a capability.
- Gemini authors a valid skill (the #1 on-disk format) from a natural-language goal.
- A closed test/fix loop: run → on failure feed the error back → fix → retry, with
  a bounded attempt budget and per-attempt timeout, installing needed deps.
- On success the skill is saved **armed** and its real-args run output is returned.
- Kel is prompted to act decisively and to narrate a short holding line while building.
- Everything testable without the network (a fake coder injected in tests).

## Non-goals (out of scope for this spec)

- The web panel (#3) and user-editable personality (#4). The prompt change here is
  a static code edit.
- Live mid-session tool injection changes — not needed, because `build_skill`
  returns the result directly (see the flow).
- A security sandbox for generated code (stability-not-security, as in #1).
- Multi-file "projects." v1 authors a single-file skill (`skill.py`). "Make me an
  app" is handled as a skill that scaffolds files and *launches* the app through
  the shell/terminal tools Kel already has — the skill's return string reports what
  it launched.
- Human-in-the-loop review of the generated code before first run (explicitly
  rejected by the Full-autonomy choice).

## Components

New package area `src/kel/skills/authoring/` (keeps the #1 runtime modules clean):

- **`contracts.py`** — `DraftSkill` (name, description, parameters dict, code:str,
  invocation_args: dict) and `AuthorOutcome` (ok: bool, skill_name: str | None,
  output: str, attempts: int, log: list[str]). Pure types.
- **`coder.py`** — a `Coder` protocol: `draft(goal, feedback) -> DraftSkill`, and a
  `GeminiCoder` implementation using `google.genai` `models.generate_content` with
  `KEL_CODER_MODEL`. It is given the skill contract (the exact `skill.json` shape,
  the `def run(**kwargs) -> str` entrypoint, "return a string", the snake_case name
  rule, "no built-in tool names") and, on a retry, the previous code + the captured
  traceback. It returns structured JSON (name/description/parameters/code/args)
  parsed into a `DraftSkill`. A `FakeCoder` (returns canned drafts) makes the loop
  testable without the network.
- **`author.py`** — `SkillAuthor.build(goal) -> AuthorOutcome`, the loop:
  1. `coder.draft(goal, feedback=None)`.
  2. Validate the draft's name (snake_case, not a built-in). If it collides with an
     existing skill, append the smallest numeric suffix that's free (`make_qr_code`
     → `make_qr_code_2`). Write `skill.py` + `skill.json` (enabled: true,
     author: "kel") into a **staging** dir under the skills root.
  3. Run it with `invocation_args` via the #1 `executor.run_skill`.
  4. **Missing dependency?** If the run failed with `ModuleNotFoundError: No module
     named 'X'` and `KEL_SKILLS_AUTHOR_ALLOW_PIP`, `pip install X` into Kel's venv
     (`sys.executable -m pip install`, bounded by a timeout) and re-run the *same*
     draft — bounded by a small install budget so a stubborn import can't loop
     forever. Handling deps reactively from the actual error avoids brittle static
     import analysis.
  5. If `ok`, keep it armed and return `AuthorOutcome(ok=True, output=<run output>)`.
     If it's a code failure (not a missing dep), capture the failure string,
     `coder.draft(goal, feedback=<failure>)`, overwrite the files, retry — up to
     `KEL_SKILLS_AUTHOR_MAX_ATTEMPTS`.
  6. On exhaustion, remove the staged skill and return `ok=False` with the last error.
  `SkillAuthor` depends on a `Coder`, a `SkillStore`, and `run_skill` — all injected,
  so tests use a `FakeCoder` and a tmp store.
- **`BUILD_SKILL_TOOL`** in `options.py` + `BUILD_SKILL_TOOL_NAME = "build_skill"`,
  gated by a new `skills_author_enabled` flag, with one string param `goal`. Added to
  `tool_specs()` like the other capability tools.
- **Dispatch** in both `session.py` and `gemini_session.py` (mirrored, per the
  codebase style): a `build_skill` call runs `SkillAuthor.build(goal)` via
  `asyncio.to_thread` and returns `outcome.output` to the model. The author is
  injected into both sessions from `app.py` (built only when author-enabled and a
  Gemini key is present).

## Personality change

`prompts/kel_personality.py` gains guidance in the realtime instructions:

- Be **decisive**: when a request is doable with reasonable assumptions, make them
  and act; don't interrogate the user with clarifying questions unless genuinely
  blocked.
- When you lack a tool/skill for what's asked, **call `build_skill` yourself** with
  a clear one-line goal — don't say you can't, and don't ask permission.
- Say a short holding line first (e.g. "give me a sec") because building takes a
  moment, then report the result.

## Configuration (following `Settings` conventions)

- `skills_author_enabled: bool = True` ← `KEL_SKILLS_AUTHOR_ENABLED` (effective only
  when a Gemini key is present; degrade to off with a printed note otherwise).
- `coder_model: str = "gemini-2.5-flash"` ← `KEL_CODER_MODEL` (any free-tier-capable
  Gemini coding model; pin the current best in the plan).
- `skills_author_max_attempts: int = 4` ← `KEL_SKILLS_AUTHOR_MAX_ATTEMPTS` (positive int).
- `skills_author_allow_pip: bool = True` ← `KEL_SKILLS_AUTHOR_ALLOW_PIP`.
- Test runs reuse `skills_timeout_seconds` from #1; pip installs get their own bound.

## Error handling

- **Coder returns junk** (unparseable JSON / no `run`): counts as a failed attempt;
  the parse error is the feedback for the next draft.
- **Skill won't compile / crashes / times out**: the #1 executor already maps these
  to a clean failure string, which becomes the coder's feedback.
- **pip install fails** (or the same module is still missing after install): captured
  and fed back to the coder as the failure, so it can pick a stdlib approach instead.
- **Budget exhausted**: staged skill removed; Kel gets "I tried a few times but
  couldn't get that working — here's what went wrong: <last error>," so she can tell
  the user honestly instead of pretending.
- **Author disabled / no Gemini key**: `build_skill` isn't offered; if somehow
  called, it replies that skill-building is off.

## Testing

A `FakeCoder` returns scripted `DraftSkill`s, so the loop is fully deterministic and
offline. Unit tests:

- Loop succeeds on the first draft → `ok=True`, output is the run result, skill
  armed on disk.
- First draft crashes, second (fed the traceback) works → `ok=True`, `attempts==2`,
  and the fake coder received the failure text as feedback.
- All drafts fail → `ok=False` after `max_attempts`, staged skill removed, last
  error in the output.
- Name collision with a built-in / existing skill is resolved (suffix) or rejected.
- pip path: a draft importing a "missing" module triggers the install step (install
  faked/stubbed in tests — no real network).
- `options.tool_specs()` offers `build_skill` only when `skills_author_enabled`.
- Both sessions dispatch a `build_skill` tool call to the injected author and return
  its output (fake author).
- `Settings.from_mapping` parses the new options and rejects a bad max-attempts.
- Personality prompt contains the decisiveness + build-skill cues.

`GeminiCoder`'s real network call is not unit-tested (like the other provider
clients in the repo); it's exercised by hand via the smoke check below.

## Manual smoke check (end-to-end, real Gemini)

With `GEMINI_API_KEY` set:

```bash
uv run python -c "from kel.config.settings import Settings; from kel.skills.authoring.app import build_author; \
a=build_author(Settings.from_env()); print(a.build('generate a QR code PNG for the text hello and save to /tmp/hello.png').output)"
```

Expect Gemini to author a `make_qr_code`-style skill, the loop to install `qrcode`
if needed, run it, and report the saved path — with the skill left armed in
`~/.kel/skills/`.

## Open choices settled by recommendation (reversible)

- **Coder default `gemini-2.5-flash`** — a strong free-tier coding model; overrideable.
- **The successful test run doubles as the real run** — avoids needing live tool
  injection and gives the user their result immediately on both brains.
- **Single-file skills only in v1** — "apps" are launched by a skill, not embedded.
