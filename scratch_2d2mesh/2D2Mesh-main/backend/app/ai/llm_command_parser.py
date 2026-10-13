"""LLM Command Parser for Natural-Language 3D Editing.

Translates a user's free-text command into a structured JSON operation dict.
The LLM generates ONLY command metadata, never 3D geometry.

Supports two backends:
1. Mock (default, no API key): keyword-based heuristic parsing
2. OpenAI: calls GPT to produce a structured command dict

Structured command schema (matches the Validation step in
`app/ai/command_validator.py`):

  {
    "operations": [
      {"type": "change_material", "target": "car_body", "value": "red"},
      {"type": "reduce_polygons", "target": "all", "value": 0.5},
    ]
  }

Operation `type` values:
  change_material | change_color | change_roughness | change_metalness
  | reduce_polygons | scale | translate | rotate | prepare_print

The parser never touches model files — it only produces the structured command
which is validated and applied downstream by the deterministic mesh editor.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from app.ai.command_validator import COLOR_KEYWORDS, MATERIAL_PRESETS

logger = logging.getLogger(__name__)


def parse_command(user_text: str, use_openai: bool = False, openai_model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """Parse a user's free-text command into a structured operations dict.

    Args:
        user_text: The user's natural-language command.
        use_openai: If True and OPENAI_API_KEY is set, use GPT for parsing.
        openai_model: Which OpenAI model to use.

    Returns:
        A structured command dict `{"operations": [...]}`, or an error dict
        `{"operation": "unknown", "error": "..."}` if parsing fails.
    """
    text = user_text.strip()
    if not text:
        return {"operation": "unknown", "error": "Empty command"}

    if use_openai:
        try:
            return _parse_with_openai(text, openai_model)
        except Exception as exc:
            logger.warning("OpenAI parsing failed (%s), falling back to mock.", exc)

    return _parse_mock(text)


def _parse_mock(text: str) -> Dict[str, Any]:
    """Keyword-based heuristic parser — no API key required.

    Emits the same `operations` array shape as the OpenAI path so the rest of
    the pipeline (validation → edit service) is backend-agnostic.
    """
    lower = text.lower()

    # Detect target mesh name (e.g. "wheels", "body", "roof")
    target = "all"
    target_match = re.search(r"\bthe\s+(\w+)", lower)
    if target_match:
        candidate = target_match.group(1)
        # skip generic words
        if candidate not in {"model", "object", "mesh", "scene", "whole", "entire", "3d"}:
            target = candidate

    operations: list[Dict[str, Any]] = []

    # ── Colour change ────────────────────────────────────────────────────────
    for keyword, hex_color in COLOR_KEYWORDS.items():
        if keyword in lower:
            op: Dict[str, Any] = {
                "type": "change_material",
                "target": target,
                "value": hex_color,
            }
            # Material preset combined with color?
            for preset in MATERIAL_PRESETS:
                if preset in lower:
                    op["value"] = preset
                    op["roughness"] = MATERIAL_PRESETS[preset]["roughness"]
                    op["metalness"] = MATERIAL_PRESETS[preset]["metalness"]
                    break
            operations.append(op)
            return {"operations": operations}

    # ── Material preset only ─────────────────────────────────────────────────
    for preset in MATERIAL_PRESETS:
        if preset in lower:
            operations.append({
                "type": "change_material",
                "target": target,
                "value": preset,
                "roughness": MATERIAL_PRESETS[preset]["roughness"],
                "metalness": MATERIAL_PRESETS[preset]["metalness"],
            })
            return {"operations": operations}

    # ── Polygon reduction ─────────────────────────────────────────────────────
    reduce_keywords = ["reduce", "simplify", "fewer polygon", "fewer triangle", "low poly", "optimize polygon"]
    if any(k in lower for k in reduce_keywords):
        # Try to extract a percentage
        pct_match = re.search(r"(\d+)\s*%", lower)
        ratio = 0.5  # default: keep 50%
        if pct_match:
            ratio = int(pct_match.group(1)) / 100.0
            ratio = max(0.05, min(0.95, ratio))
        operations.append({
            "type": "reduce_polygons",
            "target": target,
            "value": round(ratio, 3),
        })
        return {"operations": operations}

    # ── Scale ────────────────────────────────────────────────────────────────
    if "scale" in lower or "resize" in lower or "bigger" in lower or "smaller" in lower:
        factor_match = re.search(r"(\d+(?:\.\d+)?)\s*[xX\u00d7]", lower)
        factor = 1.5 if "bigger" in lower else 0.7 if "smaller" in lower else 1.0
        if factor_match:
            factor = float(factor_match.group(1))
        operations.append({"type": "scale", "target": target, "value": factor})
        return {"operations": operations}

    # ── 3D print preparation ─────────────────────────────────────────────────
    if any(k in lower for k in ["print", "3d print", "printable", "printing"]):
        operations.append({"type": "prepare_print", "target": target})
        return {"operations": operations}

    # ── Roughness / smoothness ────────────────────────────────────────────────
    if "roughness" in lower or "rough" in lower or "smooth" in lower:
        val = 0.8 if "rough" in lower else 0.1
        val_match = re.search(r"(\d+(?:\.\d+)?)", lower)
        if val_match:
            num = float(val_match.group(1))
            val = num if num <= 1.0 else num / 100.0
        operations.append({
            "type": "change_roughness",
            "target": target,
            "value": round(val, 2),
        })
        return {"operations": operations}

    # ── Metalness ────────────────────────────────────────────────────────────
    if "metalness" in lower or "metallic" in lower:
        val_match = re.search(r"(\d+(?:\.\d+)?)", lower)
        val = 0.9
        if val_match:
            num = float(val_match.group(1))
            val = num if num <= 1.0 else num / 100.0
        operations.append({
            "type": "change_metalness",
            "target": target,
            "value": round(val, 2),
        })
        return {"operations": operations}

    # Fallback
    return {
        "operation": "unknown",
        "error": f"Could not parse command: '{text}'. Try: 'Make it red', 'Reduce polygons by 50%', 'Make it metallic'.",
    }


def _parse_with_openai(text: str, model: str) -> Dict[str, Any]:
    """Use OpenAI to parse the command into a structured operations dict."""
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY from env

    system_prompt = """You are a 3D model editing command parser.
The user gives you a natural-language instruction to edit a 3D model.
You must output ONLY a JSON object (no explanation) with the following schema:
{
  "operations": [
    {
      "type": "change_material" | "change_color" | "change_roughness" | "change_metalness"
             | "reduce_polygons" | "scale" | "translate" | "rotate" | "prepare_print",
      "target": "<mesh name or 'all'>",
      "value": <string | number | [x, y, z]>
    }
  ]
}
Rules:
- "change_material"/"change_color": value is a CSS color name/hex OR a material
  preset ('metal', 'glass', 'matte', 'plastic', 'rubber', 'wood', 'concrete', 'shiny').
- "change_roughness"/"change_metalness": value is a number 0.0-1.0.
- "reduce_polygons": value is the fraction of faces to KEEP (0.05-0.95).
- "scale": value is a factor number or [x, y, z].
- "translate"/"rotate": value is [x, y, z].
- "prepare_print": no value required.
- target: the mesh the user refers to, or 'all'.
Return {"operations": []} if the command cannot be parsed.
The LLM must NOT generate geometry. Only output the command dict."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
        max_tokens=512,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    return json.loads(raw)
