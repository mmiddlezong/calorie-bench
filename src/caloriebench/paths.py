"""Filesystem locations used throughout the benchmark."""

from __future__ import annotations

import os
from pathlib import Path


def _find_root() -> Path:
    env = os.environ.get("CALORIEBENCH_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "configs").is_dir():
            return parent
    return Path.cwd()


ROOT = _find_root()
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.jsonl"
IMAGES_DIR = DATA_DIR / "images"
CONFIGS_DIR = ROOT / "configs"
MODELS_PATH = CONFIGS_DIR / "models.yaml"
PROMPTS_DIR = ROOT / "prompts"
RESULTS_DIR = ROOT / "results"
