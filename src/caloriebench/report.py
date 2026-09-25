"""Leaderboard generation (Markdown + JSON) from stored predictions."""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

from .config import Registry
from .dataset import Dish
from .metrics import ModelScore, score_model
from .paths import RESULTS_DIR
from .prompt import PROMPT_VERSION
from .runner import read_records


def discover_models(results_dir: Path = RESULTS_DIR) -> list[str]:
    base = results_dir / PROMPT_VERSION
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "predictions.jsonl").exists())


def score_all(dishes: list[Dish], model_ids: list[str], results_dir: Path = RESULTS_DIR) -> list[ModelScore]:
    scores = []
    for mid in model_ids:
        recs = read_records(results_dir / PROMPT_VERSION / mid / "predictions.jsonl")
        if recs:
            scores.append(score_model(mid, dishes, recs))
    scores.sort(key=lambda s: s.calories.get("mae_kcal", math.inf))
    return scores


def _pct(x: float | None, digits: int = 1) -> str:
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.{digits}f}%"


def _num(x: float, digits: int = 2) -> str:
    return "–" if x is None or math.isnan(x) else f"{x:.{digits}f}"


def _meta(results_dir: Path, mid: str) -> dict:
    path = results_dir / PROMPT_VERSION / mid / "meta.json"
    return json.loads(path.read_text()) if path.exists() else {}


def leaderboard_markdown(scores: list[ModelScore], registry: Registry | None, results_dir: Path = RESULTS_DIR) -> str:
    lines = [
        f"# CalorieBench leaderboard (prompt {PROMPT_VERSION})",
        "",
        f"_Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}. "
        "Ranked by mean absolute calorie error (lower is better). 95% CIs from 10,000 "
        "dish-level bootstrap resamples. Baseline rows (†) ignore the image and always guess "
        "the training-set average dish._",
        "",
        "| # | Model | Calorie MAE, kcal (95% CI) | MAE % | Within ±20% | Median APE | MAPE "
        "| Bias (kcal) | r | Fail | Cost / 100 dishes | n |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rank = 0
    for s in scores:
        spec = None
        if registry is not None:
            try:
                spec = registry.get(s.model_id)
            except KeyError:
                spec = None
        meta = _meta(results_dir, s.model_id)
        name = (spec.display_name if spec else meta.get("display_name")) or s.model_id
        is_baseline = bool(spec and spec.is_baseline)
        c = s.calories
        if not c:
            continue
        if is_baseline:
            label, rank_str = f"_{name}_ †", ""
        else:
            rank += 1
            label, rank_str = f"**{name}**", str(rank)
        lo, hi = c["mae_kcal_ci95"]
        cost = s.usage.get("cost_per_dish_usd", 0.0) * 100
        n = f"{s.n_dishes}/{s.n_total}" + ("" if s.coverage == 1 else " ⚠")
        lines.append(
            f"| {rank_str} | {label} | {c['mae_kcal']:.0f} ({lo:.0f}–{hi:.0f}) | {_pct(c['mae_pct_of_mean'], 0)} "
            f"| {_pct(c['within_20pct'], 0)} | {_pct(c['mdape'], 0)} | {_pct(c['mape'], 0)} "
            f"| {c['mean_signed_error_kcal']:+.0f} | {_num(c['pearson_r'])} "
            f"| {_pct(s.failure_rate, 0)} | {'–' if is_baseline else f'${cost:.2f}'} | {n} |"
        )

    lines += [
        "",
        "**Columns.** *MAE*: mean absolute error of total calories vs. the ground truth "
        "(computed from weighed ingredients). "
        "*MAE %*: MAE as a share of the mean true calories (Nutrition5k paper metric). "
        "*Within ±20%*: share of dishes estimated within 20% of the true value (the FDA's "
        "tolerance for nutrition labels). *Median APE* / *MAPE*: median / mean absolute "
        "percentage error. *Bias*: mean signed error (negative = underestimates). *r*: Pearson "
        "correlation of predicted vs. true calories. *Fail*: unparseable answers, refusals, "
        "and truncations (scored as predicting 0). *Cost*: actual API spend per 100 dishes at "
        "list prices. ⚠ = incomplete run.",
        "",
        "## Macronutrients and mass",
        "",
        "Mean absolute error, and in parentheses as a percentage of the mean true value "
        "(the metric used in the Nutrition5k paper).",
        "",
        "| Model | Mass (g) | Protein (g) | Carbs (g) | Fat (g) | Mean output tokens | Median latency |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in scores:
        if not s.secondary:
            continue
        name = s.model_id
        if registry is not None:
            try:
                name = registry.get(s.model_id).display_name
            except KeyError:
                pass
        cells = [
            f"{s.secondary[t]['mae']:.0f} ({_pct(s.secondary[t]['mae_pct_of_mean'], 0)})"
            if t == "mass_g"
            else f"{s.secondary[t]['mae']:.1f} ({_pct(s.secondary[t]['mae_pct_of_mean'], 0)})"
            for t in ("mass_g", "protein_g", "carbs_g", "fat_g")
        ]
        u = s.usage
        tokens = f"{u['mean_output_tokens']:.0f}" if u.get("mean_output_tokens") else "–"
        if u.get("mean_reasoning_tokens"):
            tokens += f" ({u['mean_reasoning_tokens']:.0f} reasoning)"
        latency = f"{u['median_latency_s']:.1f}s" if u.get("median_latency_s") else "–"
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {tokens} | {latency} |")
    return "\n".join(lines) + "\n"


def write_leaderboard(
    scores: list[ModelScore], registry: Registry | None, results_dir: Path = RESULTS_DIR
) -> tuple[Path, Path]:
    base = results_dir / PROMPT_VERSION
    base.mkdir(parents=True, exist_ok=True)
    md_path = base / "leaderboard.md"
    json_path = base / "leaderboard.json"
    md_path.write_text(leaderboard_markdown(scores, registry, results_dir))
    json_path.write_text(
        json.dumps(
            {
                "prompt_version": PROMPT_VERSION,
                "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "models": [s.to_dict() for s in scores],
            },
            indent=2,
        )
        + "\n"
    )
    return md_path, json_path
