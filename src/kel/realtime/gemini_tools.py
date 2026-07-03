"""Convert Kel's provider-independent tool schemas into Gemini declarations.

The tools are defined once as OpenAI-style function dicts in ``options.py``. This
module reshapes them into ``google.genai`` ``FunctionDeclaration`` objects so the
exact same tool set drives the Gemini Live brain.
"""

from __future__ import annotations

from typing import Any

from google.genai import types

_TYPE_MAP = {
    "object": "OBJECT",
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
}


def _schema(node: dict[str, Any]) -> types.Schema:
    """Translate one JSON-schema node into a Gemini ``Schema``."""
    type_name = _TYPE_MAP.get(str(node.get("type", "string")).lower(), "STRING")
    kwargs: dict[str, Any] = {"type": type_name}
    if node.get("description"):
        kwargs["description"] = node["description"]
    if node.get("enum"):
        kwargs["enum"] = [str(value) for value in node["enum"]]
    if type_name == "OBJECT":
        properties = node.get("properties") or {}
        if properties:
            kwargs["properties"] = {key: _schema(value) for key, value in properties.items()}
        required = node.get("required") or []
        if required:
            kwargs["required"] = list(required)
    if type_name == "ARRAY" and node.get("items"):
        kwargs["items"] = _schema(node["items"])
    return types.Schema(**kwargs)


def function_declarations(specs: list[dict[str, Any]]) -> list[types.FunctionDeclaration]:
    """Build a Gemini ``FunctionDeclaration`` for each OpenAI-style tool spec."""
    declarations: list[types.FunctionDeclaration] = []
    for spec in specs:
        parameters = spec.get("parameters") or {"type": "object", "properties": {}}
        has_properties = bool(parameters.get("properties"))
        declarations.append(
            types.FunctionDeclaration(
                name=spec["name"],
                description=spec.get("description", ""),
                parameters=_schema(parameters) if has_properties else None,
            )
        )
    return declarations


def gemini_tools(specs: list[dict[str, Any]]) -> list[types.Tool]:
    """Wrap every enabled tool spec in a single Gemini ``Tool``."""
    declarations = function_declarations(specs)
    if not declarations:
        return []
    return [types.Tool(function_declarations=declarations)]
