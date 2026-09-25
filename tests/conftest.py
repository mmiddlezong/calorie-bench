from __future__ import annotations

import json

import pytest

from caloriebench.config import Estimate, ModelSpec, Pricing
from caloriebench.dataset import Dish

GOOD_ANSWER = {
    "items": [
        {"name": "white rice", "grams": 150, "calories": 195},
        {"name": "chicken", "grams": 100, "calories": 165},
    ],
    "total_calories": 360,
    "total_mass_g": 250,
    "protein_g": 35,
    "carbs_g": 42,
    "fat_g": 5,
}


@pytest.fixture
def good_json() -> str:
    return json.dumps(GOOD_ANSWER)


def make_spec(**overrides) -> ModelSpec:
    base = dict(
        id="test-model",
        display_name="Test Model",
        lab="Test",
        provider="anthropic",
        model="test-model-api-id",
        pricing=Pricing(input=2.0, output=10.0, cached_input=0.2),
        estimate=Estimate(image_tokens=400, reasoning_tokens=1000),
        api_key_env=["CALORIEBENCH_TEST_KEY"],
        timeout_s=10,
    )
    base.update(overrides)
    return ModelSpec(**base)


@pytest.fixture
def spec_factory():
    return make_spec


def make_dish(index: int, calories: float, **kw) -> Dish:
    return Dish(
        index=index,
        dish_id=kw.get("dish_id", f"dish_{index}"),
        calories=calories,
        mass_g=kw.get("mass_g", 200.0),
        protein_g=kw.get("protein_g", 10.0),
        carbs_g=kw.get("carbs_g", 20.0),
        fat_g=kw.get("fat_g", 5.0),
        ingredients=(),
        image=f"images/dish_{index}.png",
        image_url="",
        image_sha256="",
        calorie_stratum=0,
    )


@pytest.fixture
def dish_factory():
    return make_dish


@pytest.fixture(autouse=True)
def _test_key(monkeypatch):
    monkeypatch.setenv("CALORIEBENCH_TEST_KEY", "sk-test")
