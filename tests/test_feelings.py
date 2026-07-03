"""Feelings map to RGB colours for the body LED."""

from __future__ import annotations

from kel.body.feelings import color_for


def test_known_feelings_map_to_colors() -> None:
    assert color_for("happy") == (0, 255, 0)
    assert color_for("alert") == (255, 0, 0)


def test_feeling_is_case_insensitive() -> None:
    assert color_for("Excited") == color_for("excited")


def test_normal_is_a_dim_neutral() -> None:
    assert color_for("normal") == (30, 30, 30)


def test_unknown_feeling_falls_back_to_normal() -> None:
    assert color_for("flummoxed") == color_for("normal")
