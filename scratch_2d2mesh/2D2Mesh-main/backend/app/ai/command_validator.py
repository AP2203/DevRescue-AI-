"""Structured command validation for Natural-Language 3D Editing.

This module is the **Validation** step of the NL-edit pipeline:

    User Command → LLM → Structured JSON Operation → Validation → 3D Editing
    Service → Updated Model → Quality Check → Save New Version

The LLM only interprets the user's words and returns a structured command
(a list of operations). This validator checks that structure is safe, typed,
and within the supported operation set *before* any mesh bytes are touched.
It never modifies 3D geometry — it only normalizes/clamps the command.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Allowed operation types ─────────────────────────────────────────────────
ALLOWED_OPERATIONS = {
    "change_material",
    "change_color",
    "change_roughness",
    "change_metalness",
    "reduce_polygons",
    "scale",
    "translate",
    "rotate",
    "prepare_print",
}

# Operations that require a `value` field.
OPERATIONS_REQUIRING_VALUE = ALLOWED_OPERATIONS - {"prepare_print"}

# ── Color keyword map (same palette as the parser) ──────────────────────────
COLOR_KEYWORDS = {
    "red": "#ff0000", "blue": "#0000ff", "green": "#00aa00",
    "yellow": "#ffff00", "orange": "#ff8800", "purple": "#8800ff",
    "black": "#000000", "white": "#ffffff", "grey": "#888888",
    "gray": "#888888", "brown": "#8b4513", "pink": "#ff69b4",
    "cyan": "#00ffff", "magenta": "#ff00ff", "gold": "#ffd700",
    "silver": "#c0c0c0", "bronze": "#cd7f32", "beige": "#f5f5dc",
    "turquoise": "#40e0d0", "navy": "#001f5b", "teal": "#008080",
    "maroon": "#800000", "lime": "#32cd32", "indigo": "#4b0082",
    "violet": "#ee82ee", "coral": "#ff7f50",
}

MATERIAL_PRESETS = {
    "metal": {"roughness": 0.2, "metalness": 0.9},
    "metallic": {"roughness": 0.2, "metalness": 0.9},
    "glass": {"roughness": 0.0, "metalness": 0.0},
    "matte": {"roughness": 0.9, "metalness": 0.0},
    "plastic": {"roughness": 0.5, "metalness": 0.0},
    "rubber": {"roughness": 0.9, "metalness": 0.0},
    "wood": {"roughness": 0.7, "metalness": 0.0},
    "concrete": {"roughness": 0.85, "metalness": 0.0},
    "shiny": {"roughness": 0.05, "metalness": 0.3},
}

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalize_color(value: Any) -> Optional[str]:
    """Resolve a CSS color name or hex string to a normalized '#rrggbb' value.

    Returns None when the value is not a recognizable color.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate in COLOR_KEYWORDS:
        return COLOR_KEYWORDS[candidate]
    if _HEX_RE.match(candidate):
        hex_str = candidate.lstrip("#")
        if len(hex_str) == 3:
            hex_str = "".join(ch * 2 for ch in hex_str)
        return f"#{hex_str.lower()}"
    return None


def _clamp_01(value: Any) -> Optional[float]:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return round(min(1.0, max(0.0, num)), 3)


def _as_positive_float(value: Any) -> Optional[float]:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num <= 0:
        return None
    return round(num, 4)


def _as_vec3(value: Any) -> Optional[List[float]]:
    if isinstance(value, (int, float)):
        num = float(value)
        if num <= 0:
            return None
        return [round(num, 4)] * 3
    if isinstance(value, (list, tuple)) and len(value) == 3:
        out = []
        for item in value:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                return None
        return out
    return None


class CommandValidationError(ValueError):
    """Raised when a structured command fails validation.

    Kept as a distinct type so the edit service can translate it into a
    400 `ValidationError` response without losing machine-readable details.
    """

    def __init__(self, message: str, details: Optional[List[Dict[str, Any]]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []


def validate_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize a structured command.

    Expected shape:

        {"operations": [{"type": "change_material", "target": "car_body",
                         "value": "red"}, ...]}

    Returns a normalized copy with `operations` guaranteed to be a non-empty
    list of valid operations. Raises `CommandValidationError` on failure.
    """
    if not isinstance(command, dict):
        raise CommandValidationError("Structured command must be a JSON object")

    operations = command.get("operations")
    if not isinstance(operations, list) or len(operations) == 0:
        raise CommandValidationError(
            "Structured command must contain a non-empty 'operations' array"
        )

    validated_ops: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for index, raw_op in enumerate(operations):
        op = _validate_operation(raw_op, index)
        if op is None:
            continue
        if "error" in op:
            errors.append({"operation_index": index, **op})
        else:
            validated_ops.append(op)

    if errors:
        raise CommandValidationError(
            f"{len(errors)} operation(s) failed validation", details=errors
        )
    if not validated_ops:
        raise CommandValidationError("No valid operations to apply")

    normalized = dict(command)
    normalized["operations"] = validated_ops
    return normalized


def _validate_operation(raw_op: Any, index: int) -> Dict[str, Any]:
    if not isinstance(raw_op, dict):
        return {"error": "operation must be a JSON object"}

    op_type = raw_op.get("type")
    if not isinstance(op_type, str) or op_type not in ALLOWED_OPERATIONS:
        return {
            "error": f"Unknown operation type '{op_type}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_OPERATIONS))}."
        }

    target = raw_op.get("target", "all")
    if not isinstance(target, str) or not target.strip():
        return {"error": "operation 'target' must be a non-empty string"}
    target = target.strip()

    value = raw_op.get("value")
    if op_type in OPERATIONS_REQUIRING_VALUE and value is None:
        return {"error": f"Operation '{op_type}' requires a 'value' field"}

    op: Dict[str, Any] = {"type": op_type, "target": target}

    if op_type in ("change_material", "change_color"):
        color = normalize_color(value)
        if color is None and isinstance(value, str) and value.strip().lower() in MATERIAL_PRESETS:
            preset = MATERIAL_PRESETS[value.strip().lower()]
            op["value"] = value.strip().lower()
            op["roughness"] = preset["roughness"]
            op["metalness"] = preset["metalness"]
        elif color is not None:
            op["value"] = color
        else:
            return {
                "error": f"'{value}' is not a valid color or material preset "
                f"(presets: {', '.join(sorted(MATERIAL_PRESETS))})"
            }
    elif op_type in ("change_roughness", "change_metalness"):
        num = _clamp_01(value)
        if num is None:
            return {"error": f"'{value}' is not a valid 0-1 number for '{op_type}'"}
        op["value"] = num
    elif op_type == "reduce_polygons":
        num = _clamp_01(value)
        if num is None:
            return {"error": "reduce_polygons 'value' must be a 0-1 ratio"}
        # Clamp to a sane reduction window (keep 5%-95% of faces).
        op["value"] = round(min(0.95, max(0.05, num)), 3)
    elif op_type == "scale":
        vec = _as_vec3(value)
        if vec is None:
            return {"error": "scale 'value' must be a positive number or [x, y, z]"}
        op["value"] = vec
    elif op_type in ("translate", "rotate"):
        vec = _as_vec3(value)
        if vec is None:
            return {"error": f"'{op_type}' 'value' must be [x, y, z]"}
        op["value"] = vec
    elif op_type == "prepare_print":
        op.pop("value", None)

    return op
