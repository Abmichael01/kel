# Kel system actions (browser + terminal)

Kel can act on the computer through tools it calls on its own, like the camera and
memory tools.

## Browser (low risk, on by default)

- `open_url` — opens a URL in your default browser.
- `web_search` — opens a web search for a query.

Say things like "Kel, open YouTube" or "Kel, search for the weather." Uses Python's
`webbrowser`, so it opens in whatever your system browser is.

```text
KEL_BROWSER_ENABLED=true
```

## Terminal (powerful — opt in)

There are two ways Kel runs things:

- **`run_command`** — runs a quick command, waits, and reads the output back. Good
  for "what's my IP", "list these files". Blocks until it finishes (or the timeout),
  so it is **not** for long-running things.
- **`run_in_terminal`** — launches a command in its **own terminal window**,
  detached, and returns immediately. Kel keeps chatting, the process keeps running,
  and you can watch it. Use it for apps, dev servers, players, `htop`, tailing logs.
  Set `KEL_TERMINAL` to pick the emulator, or leave it empty to auto-detect
  (konsole, alacritty, kitty, foot, gnome-terminal, xterm). With no terminal found
  it falls back to running detached in the background.

Both are **unrestricted** by your choice: Kel runs whatever command it decides on,
no allowlist, no confirmation.

## Typing (type where you click)

`type_text` types into whatever text box you've **focused** (clicked into) — a
search bar, a form field, anywhere — and `press_key` presses a single key like
Return or Tab. Kel does not move the cursor; you aim it, she types what you dictate.

### One-shot direct and smart typing

Normal conversation supports two one-shot styles without entering typing mode:

- **Direct:** “type exactly `meeting at five`” preserves those words and types them.
- **Smart:** “write a friendly reply declining the meeting” lets Kel compose the
  finished reply and type it into the focused field.

For either style, Kel calls the keyboard tool first. It does not narrate a preamble
or read the content aloud before acting; after the text is in the field, it gives a
short confirmation. If you want every later utterance copied literally instead,
use continuous typing mode.

### Continuous typing mode

Focus a text field, then say **“typing mode.”** Kel confirms once and switches from
AI conversation to direct dictation: each later speech transcript is typed into
the focused field without sending it through the model for a reply.

- Say `the future is bright` to type that text.
- Say **“space”** by itself to insert an explicit space.
- Say **“new line”** by itself to press Return and continue on a new line.
- End an utterance with **“enter”** to remove that final command word and press
  Return after typing the rest.
- Say **“stop typing”**, **“typing mode off”**, or **“exit typing mode”** to return to
  normal conversation. These exit phrases are not typed.

Typing mode stays active across multiple utterances and presses a real Space key
between them. Pressing Enter starts a fresh line without an automatic leading space.
Dictated text is not added to Kel's long-term memory. Keep the intended text field
focused: keyboard tools always target whichever application currently has focus.

Saying **“swipe left”** or **“swipe right”** calls the allowlisted
`swipe_desktop` action. On this computer it calls Niri's native
`focus-column-left` or `focus-column-right` action. This is more reliable than
synthesizing `Super+Left` or `Super+Right` through a Wayland virtual keyboard.
Other desktops still receive those fixed shortcuts as a fallback; no arbitrary
shortcut can be passed through this action.

```text
KEL_KEYBOARD=     # empty auto-detects; or set xdotool, ydotool, or wtype
```

Install the matching tool if it's missing: `xdotool` on X11, or `ydotool`/`wtype`
on Wayland. This computer runs Niri, where `wtype` is the lightweight option with
no background daemon. These tools are enabled together with the shell
(`KEL_SHELL_ENABLED`).

Kel gives `wtype` a small delay between keystrokes. Some browser and rich-text
fields drop characters or boundary spaces when a virtual keyboard sends an entire
phrase at zero delay.

```text
KEL_SHELL_ENABLED=false          # off by default; set true to allow it
KEL_SHELL_TIMEOUT_SECONDS=20     # a command is stopped if it runs longer
KEL_SHELL_BLOCK_DANGEROUS=true   # tripwire for catastrophic commands (keep on)
```

To launch an app that should keep running (a browser, editor, music player), the
command should end with ` &` so it backgrounds instead of being stopped at the
timeout.

### The one guard

Even with unrestricted shell, a small **tripwire** refuses a handful of
catastrophic, irreversible commands — wiping the disk or your home directory
(`rm -rf /`, `rm -rf ~`, `mkfs`, `dd of=/dev/...`, fork bombs). This exists because
voice is mis-heard often (we spent a lot of effort on false wakes), and a mis-heard
"free up space" must not be able to destroy the machine. It is **not** a complete
safety net — it only blocks the most obvious disasters. Turn it off at your own risk
with `KEL_SHELL_BLOCK_DANGEROUS=false`.

### Risks (be honest with yourself)

- Kel decides commands from speech it transcribed; transcription and wake detection
  are imperfect. A wrong guess runs for real.
- Output is captured and truncated to ~2000 characters and read back to Kel.
- There is no sandbox — commands run as your user, with your permissions.

## Modules

- `system/browser.py` — `Browser`: `open_url`, `search`.
- `system/keyboard.py` — `Keyboard`: focused-field typing and key presses.
- `realtime/dictation.py` — parses type-mode text, Enter, and exit phrases.
- `system/launcher.py` — `TerminalLauncher`: detached commands in a new terminal.
- `system/shell.py` — `ShellRunner.run` + `is_dangerous` tripwire.
- Tools wired in `realtime/options.py`; handlers in `realtime/session.py`.
