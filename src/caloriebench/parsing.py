"""Turn a model's raw text response into a validated prediction.

Structured-output modes usually return clean JSON, but not every model/provider supports
them, so this parser is deliberately forgiving about *format* (code fences, surrounding
prose, numbers written as strings like "450 kcal") while strict about *content*
(total_calories must be a finite, non-negative number).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field

TARGET_FIELDS = ("total_calories", "total_mass_g", "protein_g", "carbs_g", "fat_g")

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


@dataclass
class Prediction:
    total_calories: float
    total_mass_g: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    items: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class ParseError(ValueError):
    pass


def _to_number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        cleaned = value.replace(",", "")
        match = _NUMBER_RE.search(cleaned)
        if not match:
            return None
        num = float(match.group())
    else:
        return None
    return num if math.isfinite(num) else None


def _json_candidates(text: str):
    """Yield substrings that might be the JSON object, most likely first."""
    stripped = text.strip()
    yield stripped
    for block in _FENCE_RE.findall(text):
        yield block.strip()
    # Every balanced {...} span, outermost first, scanning left to right.
    depth, start = 0, None
    in_str, escape = False, False
    for i, ch in enumerate(text):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                yield text[start : i + 1]


def _load_object(text: str) -> dict:
    last_error = "no JSON object found"
    for candidate in _json_candidates(text):
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError as e:
            last_error = f"invalid JSON: {e.msg}"
            continue
        if isinstance(obj, dict) and "total_calories" in obj:
            return obj
        if isinstance(obj, dict):
            last_error = "JSON object has no total_calories field"
    raise ParseError(last_error)


def parse_prediction(text: str | None) -> Prediction:
    if not text or not text.strip():
        raise ParseError("empty response")
    obj = _load_object(text)

    values: dict[str, float | None] = {}
    for key in TARGET_FIELDS:
        num = _to_number(obj.get(key))
        if num is not None and num < 0:
            num = None
        values[key] = num
    if values["total_calories"] is None:
        raise ParseError(f"total_calories is not a valid non-negative number: {obj.get('total_calories')!r}")

    items = []
    raw_items = obj.get("items")
    if isinstance(raw_items, list):
        for it in raw_items:
            if isinstance(it, dict):
                items.append(
                    {
                        "name": str(it.get("name", ""))[:200],
                        "grams": _to_number(it.get("grams")),
                        "calories": _to_number(it.get("calories")),
                    }
                )

    return Prediction(
        total_calories=values["total_calories"],
        total_mass_g=values["total_mass_g"],
        protein_g=values["protein_g"],
        carbs_g=values["carbs_g"],
        fat_g=values["fat_g"],
        items=items,
    )
