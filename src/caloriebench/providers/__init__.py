"""Provider factory."""

from __future__ import annotations

from ..config import ModelSpec
from .base import Provider, ProviderError, ProviderResult, Usage

__all__ = ["Provider", "ProviderError", "ProviderResult", "Usage", "make_provider"]


def make_provider(spec: ModelSpec) -> Provider:
    """Instantiate the provider for a model spec (imports SDKs lazily)."""
    if spec.provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(spec)
    if spec.provider == "openai":
        from .openai_provider import OpenAIResponsesProvider

        return OpenAIResponsesProvider(spec)
    if spec.provider in ("xai", "openrouter", "openai_chat"):
        from .openai_chat_provider import OpenAIChatProvider

        return OpenAIChatProvider(spec)
    if spec.provider == "google":
        from .google_provider import GoogleProvider

        return GoogleProvider(spec)
    if spec.provider == "baseline":
        from .baseline_provider import BaselineProvider

        return BaselineProvider(spec)
    raise ValueError(f"Unknown provider {spec.provider!r} for model {spec.id}")
