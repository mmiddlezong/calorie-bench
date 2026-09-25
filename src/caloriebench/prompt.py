"""The benchmark prompt and output schema.

The prompt is versioned: results are stored under results/<PROMPT_VERSION>/ and a run
refuses to resume if the prompt text has changed. Bump PROMPT_VERSION whenever the
wording or schema changes so results from different prompts are never mixed.
"""

from __future__ import annotations

import hashlib
import json

PROMPT_VERSION = "v1"

PROMPT = """\
Estimate the nutritional content of the meal in this photo.

The photo was taken from directly above a single plate, bowl, or container of food in a \
cafeteria. Estimate the totals for ALL of the food on that plate as served (not a standard \
serving size). Ignore the dishware itself and anything that is not on the plate.

First list each food item you can identify with your estimate of its weight in grams and \
its calories. Then give totals for the whole plate:
- total_calories: kilocalories (kcal)
- total_mass_g: total weight of the food in grams (excluding the dishware)
- protein_g, carbs_g, fat_g: grams of each macronutrient

Respond with a single JSON object and nothing else, in exactly this format:
{"items": [{"name": "<food>", "grams": <number>, "calories": <number>}], \
"total_calories": <number>, "total_mass_g": <number>, "protein_g": <number>, \
"carbs_g": <number>, "fat_g": <number>}"""

# JSON Schema used for providers that support constrained/structured output. Kept to the
# common subset every provider accepts: no numeric bounds, all fields required, no extras.
OUTPUT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "grams": {"type": "number"},
                    "calories": {"type": "number"},
                },
                "required": ["name", "grams", "calories"],
                "additionalProperties": False,
            },
        },
        "total_calories": {"type": "number"},
        "total_mass_g": {"type": "number"},
        "protein_g": {"type": "number"},
        "carbs_g": {"type": "number"},
        "fat_g": {"type": "number"},
    },
    "required": ["items", "total_calories", "total_mass_g", "protein_g", "carbs_g", "fat_g"],
    "additionalProperties": False,
}

SCHEMA_NAME = "nutrition_estimate"


def prompt_hash() -> str:
    """Fingerprint of everything that defines the task as seen by the model."""
    blob = json.dumps({"prompt": PROMPT, "schema": OUTPUT_SCHEMA}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
