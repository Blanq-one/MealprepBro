"""The transport JSON schema sent to the provider, derived from the Pydantic response models (§6.3).

Groq's strict mode wants: every property required, `additionalProperties: false` on every object,
nullable fields as unions with null, and only a small keyword subset. Bounds (lengths, min/max) are moved
into the descriptions; Pydantic still enforces them on the way back, in both modes.
"""

import copy
from typing import Any

from pydantic import BaseModel

_BOUND_KEYS = (
    "minLength",
    "maxLength",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minItems",
    "maxItems",
)
_DROP_KEYS = frozenset({"title", "default", "pattern", "format", "examples", *_BOUND_KEYS})


def _bounds_hint(node: dict[str, Any]) -> str | None:
    parts = []
    labels = {
        "minLength": "min length",
        "maxLength": "max length",
        "minimum": "≥",
        "maximum": "≤",
        "exclusiveMinimum": ">",
        "exclusiveMaximum": "<",
        "minItems": "min items",
        "maxItems": "max items",
    }
    for key in _BOUND_KEYS:
        if key in node:
            parts.append(f"{labels[key]} {node[key]}")
    return ", ".join(parts) or None


def transport_schema(model: type[BaseModel]) -> dict[str, Any]:
    raw = model.model_json_schema()
    defs: dict[str, Any] = raw.pop("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            target = copy.deepcopy(defs[node["$ref"].rsplit("/", 1)[-1]])
            siblings = {k: v for k, v in node.items() if k != "$ref"}
            target.update(siblings)
            return resolve(target)
        hint = _bounds_hint(node)
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in _DROP_KEYS:
                continue
            if key == "properties":
                out[key] = {name: resolve(prop) for name, prop in value.items()}
            else:
                out[key] = resolve(value)
        if hint:
            out["description"] = f"{out['description']} ({hint})" if "description" in out else f"({hint})"
        if out.get("type") == "object" and "properties" in out:
            out["required"] = list(out["properties"])
            out["additionalProperties"] = False
            out.pop("description", None)  # model docstrings are for developers; they cost tokens every call
        return out

    schema: dict[str, Any] = resolve(raw)
    return schema


def schema_summary(schema: dict[str, Any], indent: int = 0) -> str:
    """A compact outline of the schema for the best-effort system prompt."""
    lines: list[str] = []
    pad = "  " * indent

    def type_of(node: dict[str, Any]) -> str:
        if "enum" in node:
            return "one of " + " | ".join(str(v) for v in node["enum"])
        if "anyOf" in node:
            return " or ".join(type_of(n) for n in node["anyOf"])
        if node.get("type") == "array":
            return f"list of {type_of(node.get('items', {}))}"
        return str(node.get("type", "any"))

    for name, prop in schema.get("properties", {}).items():
        desc = f"  # {prop['description']}" if "description" in prop else ""
        items = prop.get("items", {})
        if prop.get("type") == "array" and items.get("type") == "object":
            lines.append(f"{pad}{name}: list of objects{desc}")
            lines.append(schema_summary(items, indent + 1))
        elif prop.get("type") == "object":
            lines.append(f"{pad}{name}: object{desc}")
            lines.append(schema_summary(prop, indent + 1))
        else:
            lines.append(f"{pad}{name}: {type_of(prop)}{desc}")
    return "\n".join(lines)
