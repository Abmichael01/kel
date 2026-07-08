import json
from pathlib import Path

from kel.skills.store import SkillStore


def write_skill(
    root: Path,
    name: str,
    *,
    enabled: bool = False,
    parameters: dict | None = None,
    code: str = "def run(**kwargs):\n    return 'ok'\n",
    folder: str | None = None,
) -> Path:
    directory = root / (folder or name)
    directory.mkdir(parents=True)
    manifest = {
        "name": name,
        "description": f"{name} skill",
        "parameters": parameters or {"type": "object", "properties": {}},
        "enabled": enabled,
        "author": "kel",
        "created_at": "2026-07-08T00:00:00Z",
        "version": 1,
    }
    (directory / "skill.json").write_text(json.dumps(manifest))
    (directory / "skill.py").write_text(code)
    return directory


def test_missing_root_yields_no_skills(tmp_path: Path) -> None:
    store = SkillStore(tmp_path / "does-not-exist")

    assert store.all() == []
    assert store.tool_specs() == []


def test_store_scans_and_parses_a_skill(tmp_path: Path) -> None:
    write_skill(tmp_path, "greet", enabled=True)
    store = SkillStore(tmp_path)

    skills = store.all()

    assert [s.name for s in skills] == ["greet"]
    assert skills[0].directory == tmp_path / "greet"
    assert skills[0].enabled is True


def test_armed_and_tool_specs_only_include_enabled_skills(tmp_path: Path) -> None:
    write_skill(tmp_path, "armed_one", enabled=True)
    write_skill(tmp_path, "off_one", enabled=False)
    store = SkillStore(tmp_path)

    assert [s.name for s in store.armed()] == ["armed_one"]
    assert [spec["name"] for spec in store.tool_specs()] == ["armed_one"]
    assert store.tool_specs()[0]["type"] == "function"


def test_a_skill_colliding_with_a_builtin_tool_is_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "look", enabled=True)  # "look" is a built-in tool name
    store = SkillStore(tmp_path, reserved_names=frozenset({"look"}))

    assert store.all() == []


def test_a_non_compiling_skill_is_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "broken", enabled=True, code="def run(:\n")  # syntax error
    store = SkillStore(tmp_path)

    assert store.all() == []


def test_a_folder_name_mismatch_is_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "real_name", folder="different_folder")
    store = SkillStore(tmp_path)

    assert store.all() == []


def test_invalid_parameters_are_skipped(tmp_path: Path) -> None:
    write_skill(tmp_path, "bad_params", parameters={"type": "string"})
    store = SkillStore(tmp_path)

    assert store.all() == []


def test_get_returns_a_skill_by_name(tmp_path: Path) -> None:
    write_skill(tmp_path, "greet")
    store = SkillStore(tmp_path)

    assert store.get("greet").name == "greet"
    assert store.get("nope") is None
