"""Scoring: per-model metrics, bootstrap confidence intervals, and paired comparisons.

Headline metric
---------------
Mean absolute error of total calories (kcal), also shown as a percentage of the mean true
value (the metric used in the Nutrition5k paper). MAE is symmetric and bounded for
failures; MAPE is reported as a secondary metric only, because it caps under-estimates at
100% but not over-estimates (a model answering "0 kcal" for everything would score
MAPE = 100%, better than most honest attempts) and is dominated by tiny dishes.

Conventions
-----------
* The unit of analysis is the dish. With --repeats > 1, per-dish errors are averaged over
  samples first, then aggregated over dishes (so every dish carries equal weight).
* A model failure (unparseable answer, refusal, or truncation) is scored as a prediction of
  0 for every target (absolute error = the full true value). This keeps denominators equal
  across models and makes a failure cost as much as missing the whole plate.
* Infrastructure errors (status api_error) are NOT counted against the model; those dishes
  are simply missing, and `coverage` shows how complete the run is. Re-run to fill them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .dataset import Dish
from .runner import FINAL_STATUSES

# (target in manifest, field in prediction)
TARGETS = {
    "calories": "total_calories",
    "mass_g": "total_mass_g",
    "protein_g": "protein_g",
    "carbs_g": "carbs_g",
    "fat_g": "fat_g",
}
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 0


@dataclass
class DishOutcome:
    dish: Dish
    samples: list[dict]  # final record per sample

    def predictions(self, pred_field: str) -> list[float]:
        vals = []
        for rec in self.samples:
            pred = rec.get("prediction") if rec.get("status") == "ok" else None
            v = pred.get(pred_field) if pred else None
            vals.append(float(v) if v is not None else 0.0)
        return vals


def final_records(records: list[dict]) -> dict[tuple[str, int], dict]:
    """Latest model-outcome record per (dish, sample); falls back to the latest record."""
    best: dict[tuple[str, int], dict] = {}
    for r in records:
        key = (r["dish_id"], r.get("sample", 0))
        prev = best.get(key)
        if prev is None or r.get("status") in FINAL_STATUSES or prev.get("status") not in FINAL_STATUSES:
            best[key] = r
    return best


def collect_outcomes(dishes: list[Dish], records: list[dict]) -> list[DishOutcome]:
    finals = final_records(records)
    by_dish: dict[str, list[dict]] = {}
    for (dish_id, _sample), rec in sorted(finals.items(), key=lambda kv: kv[0][1]):
        if rec.get("status") in FINAL_STATUSES:
            by_dish.setdefault(dish_id, []).append(rec)
    return [DishOutcome(d, by_dish[d.dish_id]) for d in dishes if d.dish_id in by_dish]


def per_dish_ape(outcomes: list[DishOutcome], target: str = "calories") -> np.ndarray:
    pred_field = TARGETS[target]
    out = []
    for o in outcomes:
        truth = o.dish.truth(target)
        errs = [abs(p - truth) / truth for p in o.predictions(pred_field)]
        out.append(float(np.mean(errs)))
    return np.array(out)


def per_dish_abs_error(outcomes: list[DishOutcome], target: str = "calories") -> np.ndarray:
    pred_field = TARGETS[target]
    return np.array(
        [float(np.mean([abs(p - o.dish.truth(target)) for p in o.predictions(pred_field)])) for o in outcomes]
    )


def _ratio_ci(num: np.ndarray, den: np.ndarray, n: int = BOOTSTRAP_SAMPLES) -> tuple[float, float]:
    """Bootstrap CI of sum(num)/sum(den), resampling dishes."""
    if len(num) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(num), size=(n, len(num)))
    stats = num[idx].sum(axis=1) / den[idx].sum(axis=1)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def _bootstrap_ci(values: np.ndarray, stat=np.mean, n: int = BOOTSTRAP_SAMPLES) -> tuple[float, float]:
    if len(values) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(values), size=(n, len(values)))
    stats = stat(values[idx], axis=1)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


@dataclass
class ModelScore:
    model_id: str
    n_dishes: int
    n_total: int
    coverage: float
    failure_rate: float
    status_counts: dict[str, int]
    calories: dict = field(default_factory=dict)
    secondary: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "n_dishes": self.n_dishes,
            "n_total": self.n_total,
            "coverage": self.coverage,
            "failure_rate": self.failure_rate,
            "status_counts": self.status_counts,
            "calories": self.calories,
            "secondary": self.secondary,
            "usage": self.usage,
        }


def score_model(model_id: str, dishes: list[Dish], records: list[dict]) -> ModelScore:
    outcomes = collect_outcomes(dishes, records)
    finals = final_records(records)
    counts: dict[str, int] = {}
    for rec in finals.values():
        counts[rec.get("status", "unknown")] = counts.get(rec.get("status", "unknown"), 0) + 1
    n_samples = sum(len(o.samples) for o in outcomes)
    n_failed = sum(1 for o in outcomes for r in o.samples if r.get("status") != "ok")

    score = ModelScore(
        model_id=model_id,
        n_dishes=len(outcomes),
        n_total=len(dishes),
        coverage=len(outcomes) / len(dishes) if dishes else 0.0,
        failure_rate=n_failed / n_samples if n_samples else 0.0,
        status_counts=counts,
    )
    if not outcomes:
        return score

    truth = np.array([o.dish.calories for o in outcomes])
    preds = np.array([np.mean(o.predictions("total_calories")) for o in outcomes])
    ape = per_dish_ape(outcomes, "calories")
    signed = np.array(
        [np.mean([(p - o.dish.calories) / o.dish.calories for p in o.predictions("total_calories")]) for o in outcomes]
    )
    abs_err = per_dish_abs_error(outcomes, "calories")
    within = lambda t: (ape <= t).astype(float)  # noqa: E731
    r = float(np.corrcoef(preds, truth)[0, 1]) if len(outcomes) > 2 and np.ptp(preds) > 1e-9 else float("nan")

    score.calories = {
        "mae_kcal": float(abs_err.mean()),
        "mae_kcal_ci95": _bootstrap_ci(abs_err),
        "mae_pct_of_mean": float(abs_err.mean() / truth.mean()),
        "mae_pct_of_mean_ci95": _ratio_ci(abs_err, truth),
        "mape": float(ape.mean()),
        "mape_ci95": _bootstrap_ci(ape),
        "mdape": float(np.median(ape)),
        "within_10pct": float(within(0.10).mean()),
        "within_20pct": float(within(0.20).mean()),
        "within_20pct_ci95": _bootstrap_ci(within(0.20)),
        "within_30pct": float(within(0.30).mean()),
        "mean_signed_error_kcal": float(np.mean(preds - truth)),
        "median_signed_pct_error": float(np.median(signed)),
        "pearson_r": r,
    }

    for target in ("mass_g", "protein_g", "carbs_g", "fat_g"):
        pf = TARGETS[target]
        t = np.array([o.dish.truth(target) for o in outcomes])
        err = np.array([np.mean([abs(p - o.dish.truth(target)) for p in o.predictions(pf)]) for o in outcomes])
        score.secondary[target] = {
            "mae": float(err.mean()),
            "mae_pct_of_mean": float(err.mean() / t.mean()) if t.mean() > 0 else float("nan"),
        }

    recs = list(finals.values())
    costs = [r.get("cost_usd", 0.0) or 0.0 for r in recs]
    spent = sum(r.get("cost_usd", 0.0) or 0.0 for r in records)  # includes superseded retries
    lat = [r["latency_s"] for r in recs if r.get("status") in FINAL_STATUSES and "latency_s" in r]
    outs = [r["usage"]["output_tokens"] for r in recs if r.get("usage")]
    reas = [r["usage"]["reasoning_tokens"] for r in recs if r.get("usage")]
    ins = [r["usage"]["input_tokens"] for r in recs if r.get("usage")]
    score.usage = {
        "total_cost_usd": float(spent),
        "cost_per_dish_usd": float(np.mean(costs)) if costs else 0.0,
        "projected_cost_full_run_usd": float(np.mean(costs) * len(dishes)) if costs else 0.0,
        "mean_input_tokens": float(np.mean(ins)) if ins else 0.0,
        "mean_output_tokens": float(np.mean(outs)) if outs else 0.0,
        "mean_reasoning_tokens": float(np.mean(reas)) if reas else 0.0,
        "median_latency_s": float(np.median(lat)) if lat else 0.0,
    }
    return score


@dataclass
class Comparison:
    model_a: str
    model_b: str
    n_common: int
    mae_a: float
    mae_b: float
    diff: float  # mae_a - mae_b in kcal (negative = A better)
    diff_ci95: tuple[float, float]
    p_value: float


def compare_models(dishes: list[Dish], id_a: str, recs_a: list[dict], id_b: str, recs_b: list[dict]) -> Comparison:
    """Paired bootstrap on per-dish absolute calorie error, over dishes both models answered."""
    out_a = {o.dish.dish_id: o for o in collect_outcomes(dishes, recs_a)}
    out_b = {o.dish.dish_id: o for o in collect_outcomes(dishes, recs_b)}
    common = [d for d in dishes if d.dish_id in out_a and d.dish_id in out_b]
    a = per_dish_abs_error([out_a[d.dish_id] for d in common])
    b = per_dish_abs_error([out_b[d.dish_id] for d in common])
    nan = float("nan")
    if len(common) < 2:
        return Comparison(id_a, id_b, len(common), nan, nan, nan, (nan, nan), nan)
    diffs = a - b
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    idx = rng.integers(0, len(diffs), size=(BOOTSTRAP_SAMPLES, len(diffs)))
    boot = diffs[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    p = 2 * min((boot <= 0).mean(), (boot >= 0).mean())
    return Comparison(
        id_a,
        id_b,
        len(common),
        float(a.mean()),
        float(b.mean()),
        float(diffs.mean()),
        (float(lo), float(hi)),
        float(min(1.0, p)),
    )
