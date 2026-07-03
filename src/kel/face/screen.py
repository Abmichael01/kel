"""Kel's face: glowing blue robot expressions, in the classic eyes-&-mouths style.

Each mood is a distinct eye SHAPE (rounded square, circle, ^ caret, happy arc, sleepy
line, heart, or an angry/sad slanted square) plus a mouth SHAPE (flat, smile, frown,
open, "o", tongue, wavy). One fixed blue colour on black. Blinks (and blinks when the
mood changes, to mask the swap), glances around, and opens the mouth while speaking.
Drawn on a supersampled surface for soft edges.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

EYE_COLOR = (60, 185, 245)  # the single blue theme - change this one line to retint
_BLACK = (0, 0, 0)
_SS = 2


def _M(eye, mouth, lid_in=0.0, lid_out=0.0, gaze_y=0.0):
    return dict(eye=eye, mouth=mouth, lid_in=lid_in, lid_out=lid_out, gaze_y=gaze_y)


_MOODS: dict[str, dict] = {
    "normal": _M("square", "flat"),
    "listening": _M("square", "smile"),
    "thinking": _M("circle", "flat", gaze_y=-0.45),
    "typing": _M("square", "flat"),
    "happy": _M("arc", "smile"),
    "excited": _M("caret", "open"),
    "playful": _M("circle", "tongue"),
    "love": _M("heart", "smile"),
    "calm": _M("arc", "smile"),
    "alert": _M("circle", "o"),
    "sad": _M("square", "frown", lid_out=0.4, gaze_y=0.3),
    "angry": _M("square", "frown", lid_in=0.5),
    "surprised": _M("circle", "o"),
    "confused": _M("square", "wavy", lid_in=0.28, lid_out=0.28),
    "sleeping": _M("line", "flat"),
}


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _round_poly(surf, pts, thick):
    pygame.draw.lines(surf, EYE_COLOR, False, pts, thick)
    for p in (pts[0], pts[-1]):
        pygame.draw.circle(surf, EYE_COLOR, (int(p[0]), int(p[1])), max(1, thick // 2))


def _round_line(surf, p1, p2, thick):
    _round_poly(surf, [p1, p2], thick)


# --- eye shapes (ex,ey centre; s size; vy vertical openness 0..1) ----------------

def _eye_square(surf, ex, ey, s, vy, lid_in, lid_out, inner_left):
    w = s
    h = max(s * 0.16, s * 1.05 * vy)
    rect = pygame.Rect(0, 0, int(w), int(h))
    rect.center = (int(ex), int(ey))
    pygame.draw.rect(surf, EYE_COLOR, rect, border_radius=int(min(w, h) * 0.34))
    if (lid_in > 0.01 or lid_out > 0.01) and vy > 0.5:
        top = rect.top
        if inner_left:
            ld, rd = lid_in * h, lid_out * h
        else:
            ld, rd = lid_out * h, lid_in * h
        pad = int(w * 0.55)
        pygame.draw.polygon(surf, _BLACK, [
            (rect.left - pad, 0), (rect.right + pad, 0),
            (rect.right + pad, int(top + rd)), (rect.left - pad, int(top + ld)),
        ])


def _eye_circle(surf, ex, ey, s, vy, *_):
    rect = pygame.Rect(0, 0, int(s), int(max(s * 0.16, s * vy)))
    rect.center = (int(ex), int(ey))
    pygame.draw.ellipse(surf, EYE_COLOR, rect)


def _eye_caret(surf, ex, ey, s, vy, *_):
    w = s * 0.55
    up, down, thick = s * 0.4 * vy, s * 0.16 * vy, max(2, int(s * 0.24))
    _round_poly(surf, [(ex - w, ey + down), (ex, ey - up), (ex + w, ey + down)], thick)


def _eye_arc(surf, ex, ey, s, vy, *_):
    half, amp, thick = s * 0.6, s * 0.42 * vy, max(2, int(s * 0.24))
    pts = [(ex + (i / 10 * 2 - 1) * half, ey - amp * (1 - (i / 10 * 2 - 1) ** 2))
           for i in range(11)]
    _round_poly(surf, pts, thick)


def _eye_line(surf, ex, ey, s, vy, *_):
    w, thick = s * 0.5, max(2, int(s * 0.22))
    _round_line(surf, (ex - w, ey), (ex + w, ey), thick)


def _eye_heart(surf, ex, ey, s, vy, *_):
    r = max(2, int(s * 0.3))
    oy = int(s * 0.16 * vy)
    pygame.draw.circle(surf, EYE_COLOR, (int(ex - r * 0.7), int(ey - oy)), r)
    pygame.draw.circle(surf, EYE_COLOR, (int(ex + r * 0.7), int(ey - oy)), r)
    pygame.draw.polygon(surf, EYE_COLOR, [
        (ex - s * 0.52, ey - oy + r * 0.2), (ex + s * 0.52, ey - oy + r * 0.2),
        (ex, ey + s * 0.5 * vy),
    ])


_EYES = {
    "square": _eye_square, "circle": _eye_circle, "caret": _eye_caret,
    "arc": _eye_arc, "line": _eye_line, "heart": _eye_heart,
}


# --- one morphing mouth ----------------------------------------------------------
# Every mood is the SAME mouth described by four numbers, not a different shape. Those
# numbers are eased between moods, so the mouth bends and opens from one look to the next
# (smile -> frown, closed -> "o") instead of one shape hiding and another appearing.
#   bow    signed curve: + smiles (dips at centre), - frowns
#   open   how far it parts (0 = a line, 1 = wide open)
#   wave   a confused ripple along the lip
#   tongue a playful tongue that droops below
_MOUTH_KEYS = ("bow", "open", "wave", "tongue")
_MOUTH_PARAMS: dict[str, dict[str, float]] = {
    "flat":   dict(bow=0.0, open=0.0, wave=0.0, tongue=0.0),
    "smile":  dict(bow=0.45, open=0.0, wave=0.0, tongue=0.0),
    "frown":  dict(bow=-0.45, open=0.0, wave=0.0, tongue=0.0),
    "open":   dict(bow=0.16, open=0.55, wave=0.0, tongue=0.0),
    "o":      dict(bow=0.0, open=0.60, wave=0.0, tongue=0.0),
    "tongue": dict(bow=0.42, open=0.0, wave=0.0, tongue=1.0),
    "wavy":   dict(bow=0.0, open=0.0, wave=1.0, tongue=0.0),
}


def _mouth_targets(mood: str) -> dict[str, float]:
    shape = _MOODS.get(mood, _MOODS["normal"])["mouth"]
    return _MOUTH_PARAMS.get(shape, _MOUTH_PARAMS["flat"])


def _mouth_band(surf, mx, my, w, bow, open_amt, thick, wave, tongue):
    """Draw the single mouth from its current (eased) parameters, width fixed at ±w."""
    half_thick = max(1.5, thick / 2)
    open_h = w * open_amt
    amp = bow * w
    steps = 24
    upper, lower = [], []
    for i in range(steps + 1):
        f = i / steps * 2 - 1
        x = mx + f * w
        mid = my + amp * (1 - f * f) + wave * math.sin(f * math.pi * 2) * (w * 0.16)
        gap = (open_h / 2) * math.sqrt(max(0.0, 1 - f * f))  # lens: shut at the corners
        half = max(half_thick, gap)                          # never thinner than the stroke
        upper.append((x, mid - half))
        lower.append((x, mid + half))
    pygame.draw.polygon(surf, EYE_COLOR, upper + lower[::-1])
    for end in (0, -1):  # rounded caps keep the line-theme look
        cy = (upper[end][1] + lower[end][1]) / 2
        pygame.draw.circle(surf, EYE_COLOR, (int(upper[end][0]), int(cy)), int(half_thick))
    if tongue > 0.05:
        size = int(w * 0.42 * tongue)
        if size > 1:
            centre_low = my + amp + max(half_thick, open_h / 2)
            rect = pygame.Rect(0, 0, size, size)
            rect.center = (int(mx), int(centre_low + size * 0.35))
            pygame.draw.rect(surf, EYE_COLOR, rect, border_radius=int(w * 0.2))


@dataclass
class FaceRenderer:
    """Hold the current expression and paint it onto a surface."""

    width: int = 640
    height: int = 420
    mood: str = "sleeping"
    speaking: bool = False
    scale: float = 1.0
    _eye: str = "line"
    _p: dict[str, _Eased] = field(default_factory=dict)
    _m: dict[str, _Eased] = field(default_factory=dict)
    _blink: float = 1.0
    _blinking: bool = False
    _blink_phase: float = 0.0
    _blink_at: float = 2.0
    _gaze: tuple[float, float] = (0.0, 0.0)
    _gaze_target: tuple[float, float] = (0.0, 0.0)
    _gaze_at: float = 1.5
    _t: float = 0.0
    _talk: float = 0.0

    def __post_init__(self) -> None:
        m = _MOODS.get(self.mood, _MOODS["normal"])
        self._eye = m["eye"]
        self._p = {k: _Eased(m[k], m[k]) for k in ("lid_in", "lid_out", "gaze_y")}
        mt = _mouth_targets(self.mood)
        self._m = {k: _Eased(mt[k], mt[k]) for k in _MOUTH_KEYS}

    def set_mood(self, mood: str) -> None:
        m = _MOODS.get(mood, _MOODS["normal"])
        if mood in _MOODS:
            self.mood = mood
        self._eye = m["eye"]
        for k in ("lid_in", "lid_out", "gaze_y"):
            self._p[k].target = m[k]
        # Retarget the mouth params; the ease in update() morphs the mouth into the new
        # mood instead of swapping shapes, so it always looks like the one same mouth.
        mt = _mouth_targets(mood)
        for k in _MOUTH_KEYS:
            self._m[k].target = mt[k]
        self._blinking = True  # blink to mask the eye-shape swap
        self._blink_phase = 0.0

    def set_speaking(self, speaking: bool) -> None:
        self.speaking = speaking

    def nudge_scale(self, delta: float) -> float:
        self.scale = max(0.5, min(2.2, self.scale + delta))
        return self.scale

    def look(self, x: float, y: float) -> None:
        self._gaze_target = (max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y)))
        self._gaze_at = self._t + 1.6

    def update(self, dt: float) -> None:
        self._t += dt
        rate = min(1.0, dt * 9.0)
        for eased in self._p.values():
            eased.step(rate)
        for eased in self._m.values():  # morph the mouth toward the new mood
            eased.step(rate)

        if not self._blinking and self._t >= self._blink_at and self.mood != "sleeping":
            self._blinking = True
            self._blink_phase = 0.0
        if self._blinking:
            self._blink_phase += dt / 0.16
            if self._blink_phase >= 1.0:
                self._blinking = False
                self._blink = 1.0
                self._blink_at = self._t + random.uniform(2.6, 5.5)
            else:
                self._blink = 1.0 - math.sin(self._blink_phase * math.pi) * 0.9
        else:
            self._blink = 1.0

        if self._t >= self._gaze_at:
            if random.random() < 0.6:
                self._gaze_target = (random.uniform(-0.7, 0.7), random.uniform(-0.4, 0.35))
            else:
                self._gaze_target = (0.0, 0.0)
            self._gaze_at = self._t + random.uniform(1.1, 2.6)
        gx = _lerp(self._gaze[0], self._gaze_target[0], min(1.0, dt * 6.0))
        gy = _lerp(self._gaze[1], self._gaze_target[1], min(1.0, dt * 6.0))
        self._gaze = (gx, gy)

        if self.speaking:
            # a gentle, speech-like jaw. The 0.3 floor keeps the mouth clearly open the
            # whole time she talks, so it never dips shut and flickers between syllables.
            wobble = 0.5 + 0.5 * math.sin(self._t * 15.0) * abs(math.sin(self._t * 5.5))
            self._talk = _lerp(self._talk, 0.3 + 0.7 * wobble, min(1.0, dt * 12.0))
        else:
            self._talk = _lerp(self._talk, 0.0, min(1.0, dt * 12.0))

    def draw(self, screen: pygame.Surface) -> None:
        w, h = screen.get_size()
        surf = pygame.Surface((w * _SS, h * _SS))
        self._paint(surf, w * _SS, h * _SS)
        pygame.transform.smoothscale(surf, (w, h), screen)

    def _paint(self, surf: pygame.Surface, w: int, h: int) -> None:
        surf.fill(_BLACK)
        base = min(w, h)
        s = base * 0.135 * self.scale
        gap = s * 1.25
        gx, gy = self._gaze
        cx = w / 2 + gx * base * 0.06
        cy = h * 0.40 + (gy + self._p["gaze_y"].value) * base * 0.06
        vy = self._blink if self._eye != "line" else 1.0
        lid_in, lid_out = self._p["lid_in"].value, self._p["lid_out"].value
        drawer = _EYES.get(self._eye, _eye_square)
        drawer(surf, cx - gap, cy, s, vy, lid_in, lid_out, False)
        drawer(surf, cx + gap, cy, s, vy, lid_in, lid_out, True)
        mw = int(base * 0.13)
        # Talking just adds opening on top of the mood's own parting, so speech opens and
        # closes the same mouth smoothly and it settles back to the mood when she stops.
        open_amt = self._m["open"].value + self._talk * 0.42
        _mouth_band(surf, w // 2, int(h * 0.68), mw, self._m["bow"].value, open_amt,
                    max(3, int(mw * 0.16)), self._m["wave"].value, self._m["tongue"].value)


@dataclass
class _Eased:
    value: float
    target: float

    def step(self, rate: float) -> None:
        self.value = _lerp(self.value, self.target, rate)
