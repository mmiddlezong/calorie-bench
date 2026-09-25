"""Provider interface shared by every API backend."""

from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field

from ..config import ModelSpec


@dataclass
class Usage:
    """Normalized token usage. `output_tokens` is ALL billable output tokens, including
    hidden reasoning; `reasoning_tokens` is the reasoning subset (informational).
    `input_tokens` includes cached tokens; `cached_input_tokens` is the cached subset."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cached_input_tokens: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProviderResult:
    text: str | None
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None
    request_id: str | None = None
    refused: bool = False
    truncated: bool = False
    provider_cost_usd: float | None = None  # cost reported by the API itself, if any
    served_model: str | None = None


class ProviderError(Exception):
    """Non-retryable failure in building or sending a request (bad config, auth, 400)."""


class Provider(ABC):
    def __init__(self, spec: ModelSpec):
        self.spec = spec

    @abstractmethod
    def build_request(self, image: bytes, media_type: str, prompt: str) -> dict:
        """Return the provider-specific request kwargs (pure; no network)."""

    @abstractmethod
    async def complete(self, image: bytes, media_type: str, prompt: str) -> ProviderResult:
        """Send one request and return the normalized result."""

    async def aclose(self) -> None:  # pragma: no cover - optional hook
        return None


def b64(image: bytes) -> str:
    return base64.standard_b64encode(image).decode("ascii")


def data_url(image: bytes, media_type: str) -> str:
    return f"data:{media_type};base64,{b64(image)}"
