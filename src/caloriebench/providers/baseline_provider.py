"""Trivial, free reference predictors that ignore the image entirely.

`train-mean` / `train-median` always answer with the average dish from the Nutrition5k
TRAIN split (see data/baselines.json). A useful model must beat these. They also exercise
the full run -> score pipeline without any API calls.
"""

from __future__ import annotations

import json

from ..paths import BASELINES_PATH
from .base import Provider, ProviderResult, Usage


class BaselineProvider(Provider):
    def __init__(self, spec):
        super().__init__(spec)
        table = json.loads(BASELINES_PATH.read_text())
        key = spec.params.get("statistic", spec.model)
        if key not in table:
            raise ValueError(f"Unknown baseline statistic {key!r} (have: {[k for k in table if k != 'source']})")
        self.values = table[key]

    def build_request(self, image: bytes, media_type: str, prompt: str) -> dict:
        return {"statistic": self.spec.model}

    async def complete(self, image: bytes, media_type: str, prompt: str) -> ProviderResult:
        v = self.values
        answer = {
            "items": [],
            "total_calories": v["calories"],
            "total_mass_g": v["mass_g"],
            "protein_g": v["protein_g"],
            "carbs_g": v["carbs_g"],
            "fat_g": v["fat_g"],
        }
        return ProviderResult(text=json.dumps(answer), usage=Usage(), stop_reason="baseline")
