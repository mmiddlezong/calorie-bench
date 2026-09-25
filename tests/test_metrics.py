import math

import pytest

from caloriebench.metrics import compare_models, final_records, score_model


def rec(dish, status="ok", kcal=None, sample=0, cost=0.01, **pred):
    r = {
        "dish_id": dish.dish_id,
        "sample": sample,
        "status": status,
        "cost_usd": cost,
        "usage": {"input_tokens": 700, "output_tokens": 300, "reasoning_tokens": 0, "cached_input_tokens": 0},
        "latency_s": 2.0,
    }
    if status == "ok":
        r["prediction"] = {
            "total_calories": kcal,
            "total_mass_g": pred.get("mass", 200.0),
            "protein_g": pred.get("protein", 10.0),
            "carbs_g": 20.0,
            "fat_g": 5.0,
            "items": [],
        }
    return r


def test_mae_and_percentages(dish_factory):
    dishes = [dish_factory(0, 100.0), dish_factory(1, 200.0), dish_factory(2, 400.0), dish_factory(3, 300.0)]
    recs = [rec(dishes[0], kcal=110), rec(dishes[1], kcal=150), rec(dishes[2], kcal=400), rec(dishes[3], kcal=390)]
    s = score_model("m", dishes, recs)
    c = s.calories
    assert c["mae_kcal"] == pytest.approx((10 + 50 + 0 + 90) / 4)
    assert c["mae_pct_of_mean"] == pytest.approx(37.5 / 250)
    assert c["mape"] == pytest.approx((0.10 + 0.25 + 0.0 + 0.30) / 4)
    assert c["within_20pct"] == pytest.approx(0.5)
    assert c["mean_signed_error_kcal"] == pytest.approx((10 - 50 + 0 + 90) / 4)
    lo, hi = c["mae_kcal_ci95"]
    assert lo <= c["mae_kcal"] <= hi
    assert s.coverage == 1.0 and s.failure_rate == 0.0


def test_failures_scored_as_zero_and_api_errors_excluded(dish_factory):
    dishes = [dish_factory(0, 100.0), dish_factory(1, 200.0), dish_factory(2, 300.0)]
    recs = [rec(dishes[0], kcal=100), rec(dishes[1], status="parse_error"), rec(dishes[2], status="api_error")]
    s = score_model("m", dishes, recs)
    assert s.n_dishes == 2  # api_error dish is missing, not penalized
    assert s.coverage == pytest.approx(2 / 3)
    assert s.failure_rate == pytest.approx(0.5)
    assert s.calories["mae_kcal"] == pytest.approx((0 + 200) / 2)  # failure = predicting 0


def test_final_record_prefers_model_outcome_over_later_api_error(dish_factory):
    d = dish_factory(0, 100.0)
    recs = [rec(d, status="api_error"), rec(d, kcal=120), rec(d, status="api_error")]
    finals = final_records(recs)
    assert finals[(d.dish_id, 0)]["status"] == "ok"


def test_repeats_average_per_dish(dish_factory):
    dishes = [dish_factory(0, 100.0), dish_factory(1, 100.0)]
    recs = [
        rec(dishes[0], kcal=100, sample=0),
        rec(dishes[0], kcal=140, sample=1),
        rec(dishes[1], kcal=90, sample=0),
        rec(dishes[1], kcal=110, sample=1),
    ]
    s = score_model("m", dishes, recs)
    assert s.calories["mae_kcal"] == pytest.approx((20 + 10) / 2)


def test_secondary_targets(dish_factory):
    dishes = [dish_factory(0, 100.0, mass_g=200.0, protein_g=10.0)]
    s = score_model("m", dishes, [rec(dishes[0], kcal=100, mass=150.0, protein=16.0)])
    assert s.secondary["mass_g"]["mae"] == pytest.approx(50)
    assert s.secondary["protein_g"]["mae_pct_of_mean"] == pytest.approx(0.6)


def test_usage_totals_include_superseded_records(dish_factory):
    d = dish_factory(0, 100.0)
    s = score_model("m", [d], [rec(d, status="api_error", cost=0.0), rec(d, kcal=100, cost=0.02)])
    assert s.usage["total_cost_usd"] == pytest.approx(0.02)
    assert s.usage["projected_cost_full_run_usd"] == pytest.approx(0.02)


def test_constant_predictor_has_undefined_correlation(dish_factory):
    dishes = [dish_factory(i, 100.0 + 50 * i) for i in range(5)]
    s = score_model("m", dishes, [rec(d, kcal=250.0) for d in dishes])
    assert math.isnan(s.calories["pearson_r"])


def test_compare_models_paired(dish_factory):
    dishes = [dish_factory(i, 100.0 + 10 * i) for i in range(30)]
    good = [rec(d, kcal=d.calories + 5) for d in dishes]
    bad = [rec(d, kcal=d.calories + 80) for d in dishes]
    c = compare_models(dishes, "good", good, "bad", bad)
    assert c.n_common == 30
    assert c.diff == pytest.approx(-75)
    assert c.diff_ci95[1] < 0
    assert c.p_value < 0.05


def test_readme_block_lists_complete_runs_only(dish_factory):
    from caloriebench.report import readme_block

    dishes = [dish_factory(i, 100.0 + i) for i in range(4)]
    done = score_model("done", dishes, [rec(d, kcal=d.calories + 10) for d in dishes])
    partial = score_model("partial", dishes, [rec(d, kcal=d.calories) for d in dishes[:2]])
    block = readme_block([done, partial], None)
    assert "**done**" in block and "partial" not in block
