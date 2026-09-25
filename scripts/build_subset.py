"""Build the fixed CalorieBench evaluation subset from the public Nutrition5k dataset.

This script is run ONCE by maintainers; its outputs are committed to the repo so every
benchmark run uses exactly the same dishes:

    data/manifest.jsonl    one line per dish: labels, ingredients, image URL + sha256
    data/subset_info.json  how the subset was selected (seed, filters, pool sizes)
    data/baselines.json    trivial "guess the training-set average" predictors

Selection procedure (all deterministic):
  1. Start from the official Nutrition5k RGB *test* split (so nothing overlaps the split
     that published Nutrition5k models were trained on).
  2. Keep dishes that have an overhead RGB photo (imagery/realsense_overhead/<dish>/rgb.png).
  3. Drop dishes under MIN_KCAL (tiny denominators make percentage errors meaningless).
  4. Drop dishes whose macro labels are inconsistent with their calorie label
     (|4*protein + 4*carbs + 9*fat - kcal| / kcal > ATWATER_TOL): likely label errors.
  5. Split the remaining pool into calorie deciles and draw N/10 dishes from each
     decile with a fixed seed, skipping images that fail an automated sanity check
     or are listed in EXCLUDE after manual review.
  6. Order the manifest round-robin across deciles, so any prefix (e.g. --limit 10)
     is itself calorie-balanced.

Usage:  uv run python scripts/build_subset.py
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import statistics
import sys
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from caloriebench.paths import BASELINES_PATH, DATA_DIR, IMAGES_DIR, MANIFEST_PATH  # noqa: E402

BUCKET = "https://storage.googleapis.com/nutrition5k_dataset/nutrition5k_dataset"
LIST_API = "https://storage.googleapis.com/storage/v1/b/nutrition5k_dataset/o"

N_DISHES = 100
N_STRATA = 10
SEED = 20260925
MIN_KCAL = 30.0
ATWATER_TOL = 0.25

# Dishes removed after manual review of every drawn image: {dish_id: reason}.
# Rule: exclude only if (a) most of the food is outside the frame, or (b) food that is not
# part of the labeled dish is visible. The fixed overhead camera clips the top edge of many
# large plates (~15% of images have food touching the top border); those are KEPT, as in
# the original Nutrition5k benchmark, since excluding them would bias the subset toward
# small meals. Replacements are drawn from the same calorie stratum.
EXCLUDE: dict[str, str] = {
    "dish_1562099053": "food almost entirely outside the frame",
    "dish_1565898432": "neighboring plate with unlabeled food (olives, tomatoes, carrots) in frame",
}

TARGETS = ["calories", "mass_g", "fat_g", "carbs_g", "protein_g"]


def fetch(client: httpx.Client, url: str) -> bytes:
    r = client.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def load_metadata(client: httpx.Client) -> dict[str, dict]:
    dishes: dict[str, dict] = {}
    for cafe in ("cafe1", "cafe2"):
        text = fetch(client, f"{BUCKET}/metadata/dish_metadata_{cafe}.csv").decode()
        for row in csv.reader(io.StringIO(text)):
            if not row:
                continue
            ingredients = []
            for i in range(6, len(row) - 6, 7):
                ingredients.append(
                    {
                        "id": row[i],
                        "name": row[i + 1],
                        "grams": round(float(row[i + 2]), 2),
                        "calories": round(float(row[i + 3]), 2),
                    }
                )
            dishes[row[0]] = {
                "dish_id": row[0],
                "cafe": cafe,
                "calories": float(row[1]),
                "mass_g": float(row[2]),
                "fat_g": float(row[3]),
                "carbs_g": float(row[4]),
                "protein_g": float(row[5]),
                "ingredients": ingredients,
            }
    return dishes


def list_overhead_dishes(client: httpx.Client) -> set[str]:
    dishes: set[str] = set()
    token = None
    while True:
        params = {
            "prefix": "nutrition5k_dataset/imagery/realsense_overhead/",
            "delimiter": "/",
            "maxResults": "1000",
            "fields": "prefixes,nextPageToken",
        }
        if token:
            params["pageToken"] = token
        data = client.get(LIST_API, params=params, timeout=60).json()
        dishes.update(p.rstrip("/").rsplit("/", 1)[-1] for p in data.get("prefixes", []))
        token = data.get("nextPageToken")
        if not token:
            return dishes


def read_split(client: httpx.Client, name: str) -> list[str]:
    text = fetch(client, f"{BUCKET}/dish_ids/splits/{name}.txt").decode()
    return [line.strip() for line in text.splitlines() if line.strip()]


def label_ok(d: dict) -> bool:
    if d["calories"] < MIN_KCAL or d["mass_g"] <= 0:
        return False
    atwater = 4 * d["protein_g"] + 4 * d["carbs_g"] + 9 * d["fat_g"]
    return abs(atwater - d["calories"]) / d["calories"] <= ATWATER_TOL


def image_ok(png: bytes) -> tuple[bool, str]:
    try:
        img = Image.open(io.BytesIO(png))
        img.load()
    except Exception as e:  # corrupt file
        return False, f"unreadable: {e}"
    if img.size != (640, 480):
        return False, f"unexpected size {img.size}"
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    if gray.std() < 10:
        return False, f"nearly uniform image (std={gray.std():.1f})"
    if gray.mean() < 20 or gray.mean() > 245:
        return False, f"too dark/bright (mean={gray.mean():.1f})"
    return True, ""


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True) as client:
        meta = load_metadata(client)
        overhead = list_overhead_dishes(client)
        test_ids = read_split(client, "rgb_test_ids")
        train_ids = read_split(client, "rgb_train_ids")

        test_pool = [i for i in test_ids if i in overhead and i in meta]
        eligible = [i for i in test_pool if label_ok(meta[i])]
        print(f"test split: {len(test_ids)} | with overhead photo: {len(test_pool)} | "
              f"pass label filters: {len(eligible)}")

        kcal = np.array([meta[i]["calories"] for i in eligible])
        edges = np.quantile(kcal, np.linspace(0, 1, N_STRATA + 1))
        strata: list[list[str]] = [[] for _ in range(N_STRATA)]
        for dish_id, k in zip(eligible, kcal):
            s = min(int(np.searchsorted(edges, k, side="right")) - 1, N_STRATA - 1)
            strata[s].append(dish_id)

        rng = random.Random(SEED)
        per_stratum = N_DISHES // N_STRATA
        chosen: list[list[dict]] = []
        rejected: dict[str, str] = {}
        for s, members in enumerate(strata):
            members = sorted(members)
            rng.shuffle(members)
            picks: list[dict] = []
            for dish_id in members:
                if len(picks) == per_stratum:
                    break
                if dish_id in EXCLUDE:
                    rejected[dish_id] = f"manual: {EXCLUDE[dish_id]}"
                    continue
                url = f"{BUCKET}/imagery/realsense_overhead/{dish_id}/rgb.png"
                png = fetch(client, url)
                ok, why = image_ok(png)
                if not ok:
                    rejected[dish_id] = f"auto: {why}"
                    continue
                (IMAGES_DIR / f"{dish_id}.png").write_bytes(png)
                picks.append(
                    {
                        **meta[dish_id],
                        "calorie_stratum": s,
                        "image": f"images/{dish_id}.png",
                        "image_url": url,
                        "image_sha256": hashlib.sha256(png).hexdigest(),
                    }
                )
            if len(picks) < per_stratum:
                raise SystemExit(f"stratum {s} has too few usable dishes")
            chosen.append(picks)

    # Round-robin order: every prefix of length k*N_STRATA is calorie-balanced.
    ordered = [chosen[s][r] for r in range(per_stratum) for s in range(N_STRATA)]
    with MANIFEST_PATH.open("w") as f:
        for idx, d in enumerate(ordered):
            row = {"index": idx, **d}
            for t in TARGETS:
                row[t] = round(row[t], 3)
            f.write(json.dumps(row) + "\n")

    # Trivial baselines from the TRAIN split (same label filters, no test leakage).
    train = [meta[i] for i in train_ids if i in overhead and i in meta and label_ok(meta[i])]
    baselines = {
        "source": f"Nutrition5k rgb_train split, overhead-photo dishes passing label filters (n={len(train)})",
        "train-mean": {t: round(statistics.fmean(d[t] for d in train), 3) for t in TARGETS},
        "train-median": {t: round(statistics.median(d[t] for d in train), 3) for t in TARGETS},
    }
    BASELINES_PATH.write_text(json.dumps(baselines, indent=2) + "\n")

    info = {
        "dataset": "Nutrition5k (Thames et al., CVPR 2021), https://github.com/google-research-datasets/Nutrition5k",
        "license": "CC BY 4.0",
        "split": "rgb_test_ids",
        "n_dishes": len(ordered),
        "n_strata": N_STRATA,
        "seed": SEED,
        "filters": {
            "requires_overhead_rgb": True,
            "min_kcal": MIN_KCAL,
            "atwater_tolerance": ATWATER_TOL,
        },
        "pool_sizes": {
            "test_split": len(test_ids),
            "with_overhead_photo": len(test_pool),
            "eligible_after_label_filters": len(eligible),
        },
        "stratum_kcal_edges": [round(float(e), 1) for e in edges],
        "rejected_during_draw": rejected,
        "calories": {
            "min": round(min(d["calories"] for d in ordered), 1),
            "median": round(statistics.median(d["calories"] for d in ordered), 1),
            "mean": round(statistics.fmean(d["calories"] for d in ordered), 1),
            "max": round(max(d["calories"] for d in ordered), 1),
        },
    }
    (DATA_DIR / "subset_info.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
