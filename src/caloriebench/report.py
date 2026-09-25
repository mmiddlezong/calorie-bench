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
        "dish-level bootstrap resamples._",
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
        c = s.calories
        if not c:
            continue
        rank += 1
        label, rank_str = f"**{name}**", str(rank)
        lo, hi = c["mae_kcal_ci95"]
        cost = s.usage.get("cost_per_dish_usd", 0.0) * 100
        n = f"{s.n_dishes}/{s.n_total}" + ("" if s.coverage == 1 else " ⚠")
        lines.append(
            f"| {rank_str} | {label} | {c['mae_kcal']:.0f} ({lo:.0f}–{hi:.0f}) | {_pct(c['mae_pct_of_mean'], 0)} "
            f"| {_pct(c['within_20pct'], 0)} | {_pct(c['mdape'], 0)} | {_pct(c['mape'], 0)} "
            f"| {c['mean_signed_error_kcal']:+.0f} | {_num(c['pearson_r'])} "
            f"| {_pct(s.failure_rate, 0)} | ${cost:.2f} | {n} |"
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


README_START = "<!-- LEADERBOARD:START -->"
README_END = "<!-- LEADERBOARD:END -->"
SITE_URL = "https://mmiddlezong.github.io/calorie-bench/"


def readme_block(scores: list[ModelScore], registry: Registry | None) -> str:
    """Leaderboard table for the top of the README: complete runs only."""
    done = [s for s in scores if s.calories and s.coverage >= 1]

    def spec(mid):
        try:
            return registry.get(mid) if registry is not None else None
        except KeyError:
            return None

    lines = [
        "| Rank | Model | Avg. calorie error | Within ±20% | Bias | Cost / 100 dishes |",
        "|:---:|---|---:|---:|---:|---:|",
    ]
    rank = 0
    for s in done:
        sp = spec(s.model_id)
        name = sp.display_name if sp else s.model_id
        c = s.calories
        lo, hi = c["mae_kcal_ci95"]
        err = f"**{c['mae_kcal']:.0f} kcal** <sub>({lo:.0f}–{hi:.0f})</sub>"
        rank += 1
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, str(rank))
        lab = f" <sub>{sp.lab}</sub>" if sp else ""
        cost = s.usage.get("cost_per_dish_usd", 0) * 100
        lines.append(
            f"| {medal} | **{name}**{lab} | {err} | {_pct(c['within_20pct'], 0)} "
            f"| {c['mean_signed_error_kcal']:+.0f} | ${cost:.2f} |"
        )
    n = done[0].n_total if done else 100
    lines += [
        "",
        f"<sub>Mean absolute error of total calories on {n} real cafeteria plates (95% bootstrap CI). "
        "Within ±20%: share of plates inside the FDA's nutrition-label tolerance. Bias: mean signed "
        "error (negative = underestimates). Every model at high reasoning effort. Updated "
        f"{datetime.now(UTC).strftime('%Y-%m-%d')}; full table in "
        f"[`results/{PROMPT_VERSION}/leaderboard.md`](results/{PROMPT_VERSION}/leaderboard.md).</sub>",
    ]
    return "\n".join(lines)


def update_readme(readme: Path, scores: list[ModelScore], registry: Registry | None) -> bool:
    """Replace the marked leaderboard block in the README. Returns True if it changed."""
    if not readme.exists():
        return False
    text = readme.read_text()
    if README_START not in text or README_END not in text:
        return False
    head, rest = text.split(README_START, 1)
    _, tail = rest.split(README_END, 1)
    new = f"{head}{README_START}\n{readme_block(scores, registry)}\n{README_END}{tail}"
    if new != text:
        readme.write_text(new)
        return True
    return False
