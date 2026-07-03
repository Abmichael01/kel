"""Map Kel's feelings to RGB colours for her body LED — how she glows."""

from __future__ import annotations

_NORMAL = (30, 30, 30)  # dim neutral white: her resting / normal mode

FEELINGS: dict[str, tuple[int, int, int]] = {
    "happy": (0, 255, 0),
    "good": (0, 255, 0),
    "calm": (0, 80, 255),
    "thinking": (0, 200, 200),
    "excited": (255, 160, 0),
    "playful": (160, 0, 255),
    "cheeky": (160, 0, 255),
    "alert": (255, 0, 0),
    "annoyed": (255, 0, 0),
    "angry": (255, 0, 0),
    "sad": (0, 0, 255),
    "love": (255, 0, 80),
    "normal": _NORMAL,
    "neutral": _NORMAL,
    "off": (0, 0, 0),
}


def color_for(feeling: str) -> tuple[int, int, int]:
    """Return the RGB colour for a feeling, defaulting to her normal glow."""
    return FEELINGS.get(feeling.strip().lower(), _NORMAL)
