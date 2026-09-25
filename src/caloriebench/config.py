"""Model registry: configs/models.yaml -> ModelSpec objects."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .paths import MODELS_PATH

# Default credentials / endpoints per provider. A model entry may override either.
PROVIDER_DEFAULTS: dict[str, dict] = {
    "anthropic": {"api_key_env": ["ANTHROPIC_API_KEY"]},
    "openai": {"api_key_env": ["OPENAI_API_KEY"]},
    "google": {"api_key_env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"]},
    "xai": {"api_key_env": ["XAI_API_KEY"], "base_url": "https://api.x.ai/v1"},
    "openrouter": {"api_key_env": ["OPENROUTER_API_KEY"], "base_url": "https://openrouter.ai/api/v1"},
    "baseline": {"api_key_env": []},
}


class Pricing(BaseModel):
    """USD per 1M tokens (standard, non-batch tier)."""

    input: float
    output: float
    cached_input: float | None = None


class Estimate(BaseModel):
    """Per-request token assumptions used only for pre-run cost ESTIMATES. Actual cost is
    always computed from the usage the API reports."""

    image_tokens: int = 0
    text_tokens: int = 330
    output_tokens: int = 350  # visible JSON answer
    reasoning_tokens: int = 0  # expected hidden reasoning/thinking tokens (billed as output)


class ModelSpec(BaseModel):
    id: str
    display_name: str
    lab: str
    provider: str
    model: str
    groups: list[str] = Field(default_factory=list)
    params: dict = Field(default_factory=dict)
    structured_output: bool = True
    max_output_tokens: int = 16000
    timeout_s: float = 600.0
    base_url: str | None = None
    api_key_env: list[str] | None = None
    pricing: Pricing = Field(default_factory=lambda: Pricing(input=0, output=0))
    estimate: Estimate = Field(default_factory=Estimate)
    reasoning: str = ""
    notes: str = ""
    pricing_source: str = ""
    enabled: bool = True

    @property
    def is_baseline(self) -> bool:
        return self.provider == "baseline"

    def key_envs(self) -> list[str]:
        if self.api_key_env is not None:
            return self.api_key_env
        return PROVIDER_DEFAULTS.get(self.provider, {}).get("api_key_env", [])

    def resolved_base_url(self) -> str | None:
        return self.base_url or PROVIDER_DEFAULTS.get(self.provider, {}).get("base_url")

    def api_key(self) -> str | None:
        for env in self.key_envs():
            if os.environ.get(env):
                return os.environ[env]
        return None

    def has_credentials(self) -> bool:
        return self.is_baseline or self.api_key() is not None


class Registry(BaseModel):
    pricing_checked: str = ""
    models: list[ModelSpec]

    def get(self, model_id: str) -> ModelSpec:
        for m in self.models:
            if m.id == model_id:
                return m
        raise KeyError(f"Unknown model id {model_id!r}. Run `caloriebench models` to list them.")

    def groups(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for m in self.models:
            for g in m.groups:
                out.setdefault(g, []).append(m.id)
        return out

    def select(self, names: list[str] | None) -> list[ModelSpec]:
        """Resolve model ids and/or group names. 'all' = every enabled non-baseline model."""
        if not names:
            names = ["all"]
        chosen: list[ModelSpec] = []
        groups = self.groups()
        for name in names:
            for part in name.split(","):
                part = part.strip()
                if not part:
                    continue
                if part == "all":
                    ids = [m.id for m in self.models if m.enabled and not m.is_baseline]
                elif part in groups:
                    ids = [i for i in groups[part] if self.get(i).enabled]
                else:
                    ids = [self.get(part).id]
                for i in ids:
                    spec = self.get(i)
                    if spec not in chosen:
                        chosen.append(spec)
        return chosen


def load_registry(path: Path = MODELS_PATH) -> Registry:
    raw = yaml.safe_load(path.read_text())
    defaults = raw.get("defaults", {})
    models = []
    for entry in raw["models"]:
        merged = {**defaults, **entry}
        # Deep-merge the estimate block so per-model entries can override single fields.
        if "estimate" in defaults or "estimate" in entry:
            merged["estimate"] = {**defaults.get("estimate", {}), **entry.get("estimate", {})}
        models.append(ModelSpec(**merged))
    ids = [m.id for m in models]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate model ids in {path}: {sorted(dupes)}")
    return Registry(pricing_checked=str(raw.get("pricing_checked", "")), models=models)
