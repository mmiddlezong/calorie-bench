import json

import pytest

from caloriebench.parsing import ParseError, parse_prediction


def test_clean_json(good_json):
    p = parse_prediction(good_json)
    assert p.total_calories == 360
    assert p.protein_g == 35
    assert len(p.items) == 2 and p.items[0]["name"] == "white rice"


def test_code_fence_and_prose(good_json):
    text = f"Here is my estimate:\n```json\n{good_json}\n```\nLet me know if you need more."
    assert parse_prediction(text).total_calories == 360


def test_prose_without_fence(good_json):
    text = f"Looking at the plate, I see rice and chicken. {good_json} That's my answer."
    assert parse_prediction(text).total_mass_g == 250


def test_numbers_as_strings():
    text = json.dumps(
        {
            "total_calories": "1,250 kcal",
            "total_mass_g": "400g",
            "protein_g": "30",
            "carbs_g": None,
            "fat_g": "about 12.5",
        }
    )
    p = parse_prediction(text)
    assert p.total_calories == 1250
    assert p.total_mass_g == 400
    assert p.carbs_g is None
    assert p.fat_g == 12.5


def test_braces_inside_strings(good_json):
    tricky = json.dumps({"note": "a } brace", **json.loads(good_json)})
    assert parse_prediction("prefix " + tricky).total_calories == 360


def test_picks_object_with_total_calories():
    text = 'First {"scratch": 1} then {"total_calories": 500, "total_mass_g": 300}'
    assert parse_prediction(text).total_calories == 500


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "I cannot help with that.",
        '{"calories": 300}',
        '{"total_calories": "unknown"}',
        '{"total_calories": -5}',
        '{"total_calories": NaN}',
    ],
)
def test_invalid(text):
    with pytest.raises(ParseError):
        parse_prediction(text)


def test_negative_macro_dropped():
    p = parse_prediction('{"total_calories": 100, "fat_g": -3}')
    assert p.fat_g is None
