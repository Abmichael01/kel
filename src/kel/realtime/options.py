"""Validated configuration translated into a Realtime API session payload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kel.config.settings import Settings

REALTIME_SAMPLE_RATE = 24_000

LOOK_TOOL_NAME = "look"
_LOOK_TOOL = {
    "type": "function",
    "name": LOOK_TOOL_NAME,
    "description": (
        "Take a FRESH photo through the camera and see what is in front of you right "
        "now. You have no current image until you call this. Call it automatically, "
        "yourself, before answering ANY question that depends on seeing - what "
        "something is, what the user is holding/wearing/doing/showing, colors, or text "
        "to read. Call it again for a new frame every single time; never reuse a "
        "previous image, because the view changes."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

REMEMBER_TOOL_NAME = "remember"
_REMEMBER_TOOL = {
    "type": "function",
    "name": REMEMBER_TOOL_NAME,
    "description": (
        "Save something to long-term memory so you never forget it. Use this whenever "
        "the user shares anything worth remembering - their name, preferences, people, "
        "plans, or anything personal. Store one clear, self-contained fact."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The single fact to remember, written so it stands alone.",
            }
        },
        "required": ["text"],
    },
}

OPEN_URL_TOOL_NAME = "open_url"
_OPEN_URL_TOOL = {
    "type": "function",
    "name": OPEN_URL_TOOL_NAME,
    "description": "Open a web page in the user's browser. Use a full URL like https://...",
    "parameters": {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "The full URL to open."}},
        "required": ["url"],
    },
}

WEB_SEARCH_TOOL_NAME = "web_search"
_WEB_SEARCH_TOOL = {
    "type": "function",
    "name": WEB_SEARCH_TOOL_NAME,
    "description": (
        "Open a web search in the user's browser. ONLY use this when the user explicitly "
        "asks you to search the web, google something, or look it up online. Do NOT use it "
        "to answer normal questions - answer those yourself from what you already know."
    ),
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "What to search for."}},
        "required": ["query"],
    },
}

RUN_COMMAND_TOOL_NAME = "run_command"
_RUN_COMMAND_TOOL = {
    "type": "function",
    "name": RUN_COMMAND_TOOL_NAME,
    "description": (
        "Run a shell command on the user's computer and get its output. Use this to do "
        "things on the machine - launch apps, manage files, check status. To launch an "
        "app that should keep running, end the command with ' &'."
    ),
    "parameters": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The shell command to run."}},
        "required": ["command"],
    },
}

RUN_IN_TERMINAL_TOOL_NAME = "run_in_terminal"
_RUN_IN_TERMINAL_TOOL = {
    "type": "function",
    "name": RUN_IN_TERMINAL_TOOL_NAME,
    "description": (
        "Launch a command in its OWN new terminal window and keep chatting. Use this "
        "for anything long-running or that should stay open - apps, dev servers, "
        "players, htop, log tails - so it keeps running and the user can watch it. Use "
        "run_command instead for quick commands where you just need the output back."
    ),
    "parameters": {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "The command to launch."}},
        "required": ["command"],
    },
}

TYPE_TEXT_TOOL_NAME = "type_text"
_TYPE_TEXT_TOOL = {
    "type": "function",
    "name": TYPE_TEXT_TOOL_NAME,
    "description": (
        "Type final text into whatever field the user has focused. ONLY use this when "
        "the user clearly asks you to type, write, or put text somewhere - never type "
        "your reply to an ordinary question or a normal chat; answer those out loud. "
        "For direct typing, preserve the exact words the user asked to type. For smart "
        "writing requests, first draft, compose, rewrite, or polish the content "
        "yourself, then pass the finished text here. Call this tool before speaking; "
        "after it succeeds, give only a brief confirmation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The complete, final text that should appear in the focused field.",
            }
        },
        "required": ["text"],
    },
}

PRESS_KEY_TOOL_NAME = "press_key"
_PRESS_KEY_TOOL = {
    "type": "function",
    "name": PRESS_KEY_TOOL_NAME,
    "description": (
        "Press a single key in the focused field, like Return (to submit/enter), Tab, "
        "BackSpace, or Escape."
    ),
    "parameters": {
        "type": "object",
        "properties": {"key": {"type": "string", "description": "Key name, e.g. Return or Tab."}},
        "required": ["key"],
    },
}

START_TYPE_MODE_TOOL_NAME = "start_type_mode"
_START_TYPE_MODE_TOOL = {
    "type": "function",
    "name": START_TYPE_MODE_TOOL_NAME,
    "description": (
        "Enter continuous voice-to-keyboard dictation. Call this ONLY when the user "
        "explicitly says 'typing mode' or 'start typing' as a command. NEVER enter it "
        "for ordinary conversation, questions, or requests - if they are just talking "
        "to you or asking you something, ANSWER them out loud; do not type. After this "
        "call, the application types later speech directly, so do not ask what to type."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}

SWIPE_DESKTOP_TOOL_NAME = "swipe_desktop"
_SWIPE_DESKTOP_TOOL = {
    "type": "function",
    "name": SWIPE_DESKTOP_TOOL_NAME,
    "description": (
        "Navigate one window column left or right on the user's desktop. Call this "
        "whenever the user says 'swipe left' or 'swipe right'. On Niri this uses its "
        "native navigation; other desktops receive Super+Left or Super+Right."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "direction": {
                "type": "string",
                "enum": ["left", "right"],
                "description": "The direction the user asked to swipe.",
            }
        },
        "required": ["direction"],
    },
}

SET_FEELING_TOOL_NAME = "set_feeling"
_SET_FEELING_TOOL = {
    "type": "function",
    "name": SET_FEELING_TOOL_NAME,
    "description": (
        "Show how you feel - it changes your face and glow. Call this naturally and "
        "often as your mood shifts: happy, sad, angry, excited, surprised, confused, "
        "playful, love, calm, alert, or normal. This is your real face; use it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "feeling": {
                "type": "string",
                "description": (
                    "happy, sad, angry, excited, surprised, confused, playful, love, "
                    "calm, alert, normal"
                ),
            }
        },
        "required": ["feeling"],
    },
}

MOVE_TOOL_NAME = "move"
_MOVE_TOOL = {
    "type": "function",
    "name": MOVE_TOOL_NAME,
    "description": (
        "Physically move your body with a gesture: 'nod' (yes), 'shake' (no), "
        "'look_left', 'look_right', 'wiggle' (a happy little shimmy), or 'center' "
        "(face forward). The servo actually performs the motion. Use it to react."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "motion": {
                "type": "string",
                "enum": ["nod", "shake", "look_left", "look_right", "wiggle", "center"],
                "description": "Which gesture to perform.",
            }
        },
        "required": ["motion"],
    },
}

RECALL_TOOL_NAME = "recall"
_RECALL_TOOL = {
    "type": "function",
    "name": RECALL_TOOL_NAME,
    "description": (
        "Run a second, specific search of long-term memory when the automatically "
        "recalled notes do not contain what you need."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look up in memory, in a few words.",
            }
        },
        "required": ["query"],
    },
}


@dataclass(frozen=True, slots=True)
class RealtimeSessionOptions:
    """Runtime options for one low-latency speech-to-speech session."""

    model: str
    voice: str
    transcription_model: str
    vad_threshold: float
    vad_silence_ms: int
    noise_reduction: str
    language: str = "en"
    sample_rate: int = REALTIME_SAMPLE_RATE
    max_output_tokens: int = 512
    vision_enabled: bool = False
    memory_enabled: bool = False
    browser_enabled: bool = False
    shell_enabled: bool = False
    body_enabled: bool = False

    @classmethod
    def from_settings(cls, settings: Settings) -> RealtimeSessionOptions:
        """Select only the settings used by the realtime concern."""
        return cls(
            model=settings.realtime_model,
            voice=settings.realtime_voice,
            transcription_model=settings.realtime_transcription_model,
            vad_threshold=settings.realtime_vad_threshold,
            vad_silence_ms=settings.realtime_vad_silence_ms,
            noise_reduction=settings.realtime_noise_reduction,
            language=settings.realtime_language,
            vision_enabled=settings.vision_enabled,
            memory_enabled=settings.memory_enabled,
            browser_enabled=settings.browser_enabled,
            shell_enabled=settings.shell_enabled,
            body_enabled=settings.body_enabled,
        )

    def api_payload(self, *, instructions: str) -> dict[str, Any]:
        """Return the current Realtime `session.update` configuration."""
        payload: dict[str, Any] = {
            "type": "realtime",
            "model": self.model,
            "output_modalities": ["audio"],
            "instructions": instructions,
            "max_output_tokens": self.max_output_tokens,
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": self.sample_rate,
                    },
                    "noise_reduction": {"type": self.noise_reduction},
                    "transcription": {
                        "model": self.transcription_model,
                        "language": self.language,
                    },
                    "turn_detection": self._turn_detection(
                        create_response=False,
                        interrupt_response=True,
                    ),
                },
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": self.sample_rate,
                    },
                    "voice": self.voice,
                    "speed": 1.0,
                },
            },
        }
        tools = self.tool_specs()
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def tool_specs(self) -> list[dict[str, Any]]:
        """Return the enabled tool definitions, provider-independent.

        These OpenAI-style function schemas are the single source of truth for
        which tools Kel has; the Gemini provider converts them to its own format.
        """
        tools: list[dict[str, Any]] = []
        if self.vision_enabled:
            tools.append(_LOOK_TOOL)
        if self.memory_enabled:
            tools.extend([_REMEMBER_TOOL, _RECALL_TOOL])
        if self.browser_enabled:
            tools.extend([_OPEN_URL_TOOL, _WEB_SEARCH_TOOL])
        if self.body_enabled:
            tools.extend([_SET_FEELING_TOOL, _MOVE_TOOL])
        if self.shell_enabled:
            tools.extend(
                [
                    _RUN_COMMAND_TOOL,
                    _RUN_IN_TERMINAL_TOOL,
                    _TYPE_TEXT_TOOL,
                    _PRESS_KEY_TOOL,
                    _START_TYPE_MODE_TOOL,
                    _SWIPE_DESKTOP_TOOL,
                ]
            )
        return tools

    def type_mode_update(self, *, enabled: bool) -> dict[str, Any]:
        """Update VAD so dictation produces transcripts without AI responses."""
        return {
            "type": "realtime",
            "audio": {
                "input": {
                    "turn_detection": self._turn_detection(
                        create_response=False,
                        interrupt_response=not enabled,
                    )
                }
            },
        }

    def _turn_detection(self, *, create_response: bool, interrupt_response: bool) -> dict[str, Any]:
        return {
            "type": "server_vad",
            "threshold": self.vad_threshold,
            "prefix_padding_ms": 300,
            "silence_duration_ms": self.vad_silence_ms,
            "create_response": create_response,
            "interrupt_response": interrupt_response,
        }
