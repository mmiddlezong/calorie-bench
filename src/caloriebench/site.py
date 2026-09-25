"""Build the static results website (site/) from stored predictions.

Writes site/data.js (a `window.CALORIEBENCH = {...}` payload, so index.html also works
when opened straight from disk) and site/thumbs/<dish>.jpg thumbnails. The page itself,
site/index.html, is hand-written and never generated.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from .config import Registry
from .dataset import Dish
from .metrics import collect_outcomes
from .paths import ROOT
from .prompt import PROMPT_VERSION
from .report import discover_models, score_all
from .runner import predictions_path, read_records

SITE_DIR = ROOT / "site"
THUMB_SIZE = (360, 270)


def _num(x, digits: int = 1):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return None
    return round(float(x), digits)


def _thumbs(dishes: list[Dish], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for d in dishes:
        target = out_dir / f"{d.dish_id}.jpg"
        if target.exists() or not d.image_path.exists():
            continue
        img = Image.open(d.image_path).convert("RGB")
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        img.save(target, quality=72, optimize=True, progressive=True)


def build_site(
    dishes: list[Dish], registry: Registry, site_dir: Path = SITE_DIR, include_incomplete: bool = False
) -> Path:
    model_ids = discover_models()
    scores = score_all(dishes, model_ids)
    if not include_incomplete:  # the public site shows finished runs only
        scores = [s for s in scores if s.coverage >= 1]

    models = []
    for s in scores:
        if not s.calories:
            continue
        try:
            spec = registry.get(s.model_id)
            name, lab, reasoning = spec.display_name, spec.lab, spec.reasoning
        except KeyError:
            name, lab, reasoning = s.model_id, "", ""
        c, u = s.calories, s.usage
        models.append(
            {
                "id": s.model_id,
                "name": name,
                "lab": lab,
                "reasoning": reasoning,
                "n": s.n_dishes,
                "coverage": _num(s.coverage, 3),
                "fail_rate": _num(s.failure_rate, 3),
                "mae": _num(c["mae_kcal"], 2),
                "mae_ci": [_num(v, 2) for v in c["mae_kcal_ci95"]],
                "mae_pct": _num(c["mae_pct_of_mean"], 4),
                "within20": _num(c["within_20pct"], 3),
                "within20_ci": [_num(v, 3) for v in c["within_20pct_ci95"]],
                "mdape": _num(c["mdape"], 4),
                "mape": _num(c["mape"], 4),
                "bias": _num(c["mean_signed_error_kcal"], 2),
                "r": _num(c["pearson_r"], 3),
                "cost_per_100": _num(u.get("cost_per_dish_usd", 0) * 100, 3),
                "total_cost": _num(u.get("total_cost_usd", 0), 4),
                "latency": _num(u.get("median_latency_s"), 2),
                "out_tokens": _num(u.get("mean_output_tokens"), 0),
                "reasoning_tokens": _num(u.get("mean_reasoning_tokens"), 0),
                "macros": {
                    t: {"mae": _num(v["mae"]), "pct": _num(v["mae_pct_of_mean"], 4)} for t, v in s.secondary.items()
                },
            }
        )

    preds: dict[str, dict] = {d.dish_id: {} for d in dishes}
    for m in models:
        for o in collect_outcomes(dishes, read_records(predictions_path(m["id"]))):
            rec = o.samples[0]
            p = rec.get("prediction") if rec.get("status") == "ok" else None
            if p is None:
                preds[o.dish.dish_id][m["id"]] = {"status": rec.get("status")}
                continue
            preds[o.dish.dish_id][m["id"]] = {
                "kcal": _num(p.get("total_calories"), 0),
                "mass": _num(p.get("total_mass_g"), 0),
                "p": _num(p.get("protein_g")),
                "c": _num(p.get("carbs_g")),
                "f": _num(p.get("fat_g")),
                "items": [
                    [str(i.get("name", ""))[:60], _num(i.get("grams"), 0), _num(i.get("calories"), 0)]
                    for i in (p.get("items") or [])[:12]
                ],
            }

    dish_rows = [
        {
            "id": d.dish_id,
            "i": d.index,
            "kcal": _num(d.calories, 0),
            "mass": _num(d.mass_g, 0),
            "p": _num(d.protein_g),
            "c": _num(d.carbs_g),
            "f": _num(d.fat_g),
            "ingredients": [[g["name"], _num(g["grams"], 0)] for g in sorted(d.ingredients, key=lambda g: -g["grams"])],
            "thumb": f"thumbs/{d.dish_id}.jpg",
            "image": d.image_url,
            "preds": preds[d.dish_id],
        }
        for d in dishes
    ]

    payload = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "prompt_version": PROMPT_VERSION,
        "n_dishes": len(dishes),
        "mean_kcal": _num(sum(d.calories for d in dishes) / len(dishes)),
        "models": models,
        "dishes": dish_rows,
    }
    site_dir.mkdir(parents=True, exist_ok=True)
    _thumbs(dishes, site_dir / "thumbs")
    out = site_dir / "data.js"
    out.write_text("window.CALORIEBENCH = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    return out
