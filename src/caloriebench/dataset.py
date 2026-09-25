"""Access to the fixed evaluation subset (data/manifest.jsonl) and its images."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import httpx

from .paths import DATA_DIR, IMAGES_DIR, MANIFEST_PATH

TARGETS = ("calories", "mass_g", "protein_g", "carbs_g", "fat_g")


@dataclass(frozen=True)
class Dish:
    index: int
    dish_id: str
    calories: float
    mass_g: float
    protein_g: float
    carbs_g: float
    fat_g: float
    ingredients: tuple[dict, ...]
    image: str
    image_url: str
    image_sha256: str
    calorie_stratum: int

    @property
    def image_path(self) -> Path:
        return DATA_DIR / self.image

    def truth(self, target: str) -> float:
        return float(getattr(self, target))

    def load_image(self) -> bytes:
        path = self.image_path
        if not path.exists():
            raise FileNotFoundError(f"Missing image {path}. Run `uv run caloriebench download` first.")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.image_sha256:
            raise ValueError(f"Checksum mismatch for {path}; re-run `caloriebench download --force`.")
        return data


def load_dishes(limit: int | None = None, manifest: Path = MANIFEST_PATH) -> list[Dish]:
    """Load the subset in manifest order. Any prefix is calorie-balanced (round-robin
    across calorie strata), so `limit=10` gives one dish per stratum."""
    dishes = []
    with manifest.open() as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            dishes.append(
                Dish(
                    index=row["index"],
                    dish_id=row["dish_id"],
                    calories=row["calories"],
                    mass_g=row["mass_g"],
                    protein_g=row["protein_g"],
                    carbs_g=row["carbs_g"],
                    fat_g=row["fat_g"],
                    ingredients=tuple(row["ingredients"]),
                    image=row["image"],
                    image_url=row["image_url"],
                    image_sha256=row["image_sha256"],
                    calorie_stratum=row["calorie_stratum"],
                )
            )
    dishes.sort(key=lambda d: d.index)
    return dishes[:limit] if limit else dishes


def manifest_hash(manifest: Path = MANIFEST_PATH) -> str:
    return hashlib.sha256(manifest.read_bytes()).hexdigest()[:16]


def dishes_hash(dish_ids, manifest: Path = MANIFEST_PATH) -> str | None:
    """Fingerprint of specific dishes (labels, ingredients, image checksum), ignoring their
    position in the manifest. Lets results survive the manifest growing: a run stays valid
    as long as every dish it has answers for is unchanged. None if any dish is missing."""
    rows = {}
    with manifest.open() as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                row.pop("index", None)
                rows[row["dish_id"]] = row
    h = hashlib.sha256()
    for dish_id in sorted(set(dish_ids)):
        if dish_id not in rows:
            return None
        h.update(json.dumps(rows[dish_id], sort_keys=True).encode())
    return h.hexdigest()[:16]


def download_images(force: bool = False, workers: int = 8) -> tuple[int, int]:
    """Fetch the subset's images from the public Nutrition5k bucket and verify checksums.
    Returns (downloaded, already_present)."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    dishes = load_dishes()

    def needs(d: Dish) -> bool:
        if force or not d.image_path.exists():
            return True
        return hashlib.sha256(d.image_path.read_bytes()).hexdigest() != d.image_sha256

    todo = [d for d in dishes if needs(d)]

    def fetch(d: Dish) -> None:
        r = httpx.get(d.image_url, timeout=60, follow_redirects=True)
        r.raise_for_status()
        if hashlib.sha256(r.content).hexdigest() != d.image_sha256:
            raise ValueError(f"Checksum mismatch downloading {d.dish_id}")
        d.image_path.write_bytes(r.content)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(fetch, todo))
    return len(todo), len(dishes) - len(todo)
