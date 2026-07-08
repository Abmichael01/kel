# Skill runtime design

**Date:** 2026-07-08
**Status:** Approved for planning
**Sub-project:** #1 of the "Kel grows her own skills" roadmap

## The bigger picture

Kel should be able to *gain new abilities over time* instead of shipping with a
fixed tool set. The full vision, to be built as four separate spec → plan →
implementation cycles:

1. **Skill runtime** *(this spec)* — a skill is generated Python that shows up as
   a real callable tool in Kel's live session. Load, expose, run, and gate skills.
2. **Skill authoring** — you ask Kel to do something she can't; a coding model
   writes a skill, tests it in the runner **until it works**, and saves it.
3. **Web control panel** — a dark/blue, deliberately un-"AI-app"-looking UI to
   browse skills, read their code, arm/disarm them, and edit personality.
4. **Personality editing** — move the personality out of a hardcoded string into
   something the panel can edit and persist.

This spec covers **only #1**. It is the foundation everything else stands on: the
authoring loop (#2) tests skills by calling this runtime's runner, and the panel
(#3) arms skills by flipping this runtime's gate.

## Decisions already locked (from brainstorming)

- **A skill is generated Python registered as a real tool** — not a saved
  playbook. Each armed skill becomes its own function declaration in the session,
  right alongside `look` / `move`, and Kel calls it directly.
- **Review-then-arm gate** — a newly created skill is saved **inactive**. Someone
  (the panel, or a CLI for now) reviews it and flips it on. The gate can be
  disabled later, but it exists by default.
- **Isolated subprocess + timeout** — every skill runs in a child process with a
  hard timeout. This buys **stability**, not security: a broken or hung skill
  cannot wedge the live voice session, and we can kill it. It does **not**
  sandbox privileges — skill code runs as the user, exactly like the existing
  `run_command` tool. That is consistent with Kel's existing unrestricted-shell
  opt-in.
- **The pygame face stays as-is.** Nothing in this roadmap touches it.

## Goals

- A skill defined entirely on disk (manifest + Python) with no code changes.
- Armed skills automatically appear as tools on **both** the OpenAI and Gemini
  brains, because they merge into the one existing source of truth.
- A newly armed skill becomes callable without restarting the app. On providers
  that support live tool updates (OpenAI Realtime `session.update`), it becomes
  callable within the **current** conversation; on providers that don't, it
  applies on the next session start (see the live-arming note below).
- Running a skill can never crash or hang the voice session.
- A skill can be run in isolation (this is what authoring #2 will drive).

## Non-goals (explicitly out of scope for this spec)

- Kel *generating* skill code — that is #2. Here, skills are hand-written or
  dropped into the skills directory to exercise the runtime.
- The web UI — that is #3. Here, a small CLI is enough to list/arm/disarm.
- Personality editing — that is #4.
- Security sandboxing of skill code (see the stability-not-security note above).
- Skills receiving Kel's live context (camera frame, memory, current mood). v1
  skills are standalone functions that take their declared args and return a
  string. Context injection can come later if a real need appears.

## What a skill is on disk

One directory per skill under the skills root (default `~/.kel/skills/`,
`KEL_SKILLS_PATH` to override). Living outside the repo is deliberate: Kel
writing skills must never dirty the git tree. (This differs from memory's
repo-relative default on purpose.)

```text
~/.kel/skills/
  make_qr_code/
    skill.json     # manifest — safe to read without executing anything
    skill.py       # implementation
```

### `skill.json` (the manifest)

```json
{
  "name": "make_qr_code",
  "description": "Generate a QR code PNG for the given text and save it to a path. Call this when the user asks to make/create a QR code.",
  "parameters": {
    "type": "object",
    "properties": {
      "text": {"type": "string", "description": "The text or URL to encode."},
      "out_path": {"type": "string", "description": "Where to save the PNG."}
    },
    "required": ["text", "out_path"]
  },
  "enabled": false,
  "author": "kel",
  "created_at": "2026-07-08T00:00:00Z",
  "version": 1
}
```

- `name` — the tool name the model sees. Must be a valid snake_case identifier.
- `description` — tells the model *when* to call it (same role as descriptions in
  `options.py`).
- `parameters` — a JSON-Schema object, identical in shape to the built-in tools,
  so it flows through the existing Gemini/OpenAI conversion untouched.
- `enabled` — **the review-then-arm gate.** `false` on creation.
- `author` / `created_at` / `version` — metadata for the panel later.

**Why manifest and code are separate files:** the store and the panel read
`skill.json` to list, describe, and arm skills **without ever importing Python**.
Only the runner (in its own subprocess) imports `skill.py`.

### `skill.py` (the implementation)

Exposes exactly one entrypoint:

```python
def run(**kwargs) -> str:
    """Receives the validated declared args, returns a string Kel reads back."""
```

The return string is what the model receives as the tool result — so it should be
a short, human-meaningful summary ("Saved QR code to /home/u/qr.png"), the same
way built-in tool results read back today.

## Components

New package `src/kel/skills/`:

- **`contracts.py`** — `Skill` dataclass (name, description, parameters dict,
  enabled, author, created_at, version, dir path) and a `SkillResult`
  (ok: bool, output: str) type. No I/O, no subprocess — pure types, easy to test.
- **`store.py`** — `SkillStore`: scans the skills root, parses each `skill.json`,
  validates it, and exposes:
  - `all() -> list[Skill]` — every skill, armed or not (for the CLI/panel).
  - `armed() -> list[Skill]` — only `enabled` skills.
  - `tool_specs() -> list[dict]` — the armed skills as OpenAI-style tool dicts,
    ready to concatenate into `RealtimeSessionOptions.tool_specs()`.
  - `arm(name)` / `disarm(name)` — flip `enabled` in the manifest and persist.
  - `get(name) -> Skill | None`.
  - Validation on scan/save: legal snake_case name, no collision with a built-in
    tool name or another skill, `parameters` is a valid JSON-Schema object,
    `skill.py` compiles (`compile()`, not import). Invalid skills are skipped
    with a logged warning rather than crashing the scan.
- **`runner.py`** — runnable as `python -m kel.skills.runner <skill_dir>`:
  reads a JSON args object from **stdin**, imports the skill module in *this*
  child process, calls `run(**args)`, prints the result string to **stdout**.
  Any exception → non-zero exit with the traceback on **stderr**.
- **`executor.py`** — the parent-side `run_skill(skill, args, timeout) ->
  SkillResult`: spawns the runner subprocess, feeds args JSON, enforces the
  timeout (kills on expiry), and maps outcomes to a `SkillResult`:
  - success → `SkillResult(ok=True, output=<stdout>)`
  - timeout → `SkillResult(ok=False, output="skill '<name>' timed out after Ns")`
  - crash/bad exit → `SkillResult(ok=False, output="skill '<name>' failed: <last stderr line>")`
- **`skills_cli.py`** — `kel skills list | arm <name> | disarm <name> | run <name> '<json>'`.
  `run` is the manual test path and the same call authoring (#2) will make.

## How skills reach the model (exposure + live injection)

**The invariant:** the full tool list is `built-in tools + armed skill specs`,
merged in exactly **one** place so both the OpenAI and Gemini paths see the same
set. Both providers already build from `RealtimeSessionOptions.tool_specs()`
(OpenAI reads it in `api_payload`; Gemini converts it in `gemini_tools.py`), so
skills need to enter that one list and nothing provider-specific changes.

*Where the merge happens is a plan-phase decision* — either the session passes
`store.tool_specs()` into `options.tool_specs(extra=...)`, or the `SkillStore` is
injected as a session dependency (like the camera/memory adapters already are)
and the session concatenates. The frozen, slotted `RealtimeSessionOptions` should
stay pure config, so injecting a mutable store *into* it is the less likely
choice. The spec fixes the contract, not the wiring: one merge, both brains.

**Dispatch:** the realtime session's tool-call handler currently maps built-in
tool names to Python. It gains a fallback: a call whose name is not built-in is
looked up in the `SkillStore`; if found and armed, `executor.run_skill(...)` runs
it and its `SkillResult.output` is returned to the model as the tool result. Not
found / not armed → a clear error string back to the model.

**Live arming:** the arm path (CLI now, #3's panel later) flips the manifest and
signals the running session that the armed set changed. On OpenAI Realtime the
session re-sends its tool list via `session.update`, so the tool is callable
within seconds. If a provider's live API does not support changing tools
mid-session (Gemini Live may require a reconnect), the change instead takes effect
on the next session — no worse than a restart, and never a crash. Either way, at
session start all armed skills load normally. The contract is "armed set changed →
re-send tools where the provider allows it, else next session."

**Which interpreter runs a skill:** the executor spawns the runner with
`sys.executable`, so skills import from the same virtualenv Kel runs in. Whether a
skill's third-party dependencies are installed is an *authoring* concern (#2), not
the runtime's.

## Configuration (following existing `Settings` conventions)

Add to the frozen `Settings` dataclass, parsed in `from_mapping`:

- `skills_enabled: bool = True` ← `KEL_SKILLS_ENABLED`
- `skills_path: str = "~/.kel/skills"` ← `KEL_SKILLS_PATH` (expanduser applied)
- `skills_timeout_seconds: int = 20` ← `KEL_SKILLS_TIMEOUT_SECONDS` (mirrors
  `shell_timeout_seconds`; must be a positive int or `ConfigurationError`)

## Data flow

Creating/arming (manual, this spec):

```text
skill.json + skill.py written to ~/.kel/skills/make_qr_code/  (enabled: false)
   -> `kel skills arm make_qr_code`  (SkillStore flips enabled -> true, persists)
       -> live session re-sends its tool list (make_qr_code now callable)
```

Calling (during a conversation):

```text
model emits tool call  make_qr_code(text=..., out_path=...)
   -> session handler: not a built-in -> SkillStore.get + armed?
       -> executor.run_skill -> subprocess `python -m kel.skills.runner <dir>`
           -> args JSON on stdin -> run(**args) -> string on stdout
       -> SkillResult.output returned to the model as the tool result
```

## Error handling

- **Bad manifest / non-compiling `skill.py`** → skipped on scan with a logged
  warning; never crashes startup or the scan.
- **Name collision** with a built-in tool or another skill → rejected; the skill
  is not exposed, warning logged.
- **Skill raises** → non-zero runner exit; executor returns
  `ok=False, output="skill '<name>' failed: <reason>"`; the model reads that and
  Kel can tell the user gracefully.
- **Skill hangs / overruns timeout** → subprocess killed; timeout `SkillResult`.
- **Skill not found / not armed at call time** → clear error string to the model.

The voice session survives every one of these.

## Testing

Fixtures: a couple of fake skill directories (a happy `echo` skill, a crashing
skill, a sleeping/slow skill), plus in-memory manifests. Unit tests:

- `SkillStore` scans a directory and returns the right `Skill`s.
- `armed()` returns only enabled skills; `tool_specs()` emits correct tool dicts.
- Collision with a built-in tool name is rejected.
- Invalid manifest / non-compiling `skill.py` is skipped, not fatal.
- `arm` / `disarm` flip `enabled`, persist, and change `armed()` output.
- `executor.run_skill` happy path returns `ok=True` with stdout.
- Timeout → `ok=False` timeout message (use the slow fixture + short timeout).
- Crash → `ok=False` failure message.
- `Settings.from_mapping` parses the three new options and rejects a bad
  timeout, matching the existing settings tests.

This mirrors the repo's existing fake-provider/contract test style, so nothing
here needs the network, a real model, or audio.

## Open choices settled by recommendation (reversible)

- **Skills live in `~/.kel/skills/`**, not the repo — keeps generated code out of
  git.
- **Per-skill function tools**, not one generic `run_skill(name, args)`
  dispatcher — matches "she has this tool now" and gives the model real per-skill
  arg schemas. If the skill count ever grows large enough to bloat the tool list,
  a dispatcher can be added later without changing the on-disk format.
