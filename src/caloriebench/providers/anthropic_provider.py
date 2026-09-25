"""Anthropic Messages API (official `anthropic` SDK).

Supported `params` in models.yaml:
  effort:   low | medium | high | xhigh | max   -> output_config.effort
  thinking: dict passed verbatim as `thinking` (e.g. {type: adaptive}); omit to use the
            model's default (adaptive on Claude 5-family models, off on Haiku 4.5)
  extra:    dict merged into the request body as-is

Refusal fallbacks are intentionally NOT enabled: a benchmark must score the model that
was asked, so a refusal is recorded as that model's failure.
"""

from __future__ import annotations

import anthropic

from ..prompt import OUTPUT_SCHEMA
from .base import Provider, ProviderError, ProviderResult, Usage, b64


class AnthropicProvider(Provider):
    def __init__(self, spec, client: anthropic.AsyncAnthropic | None = None):
        super().__init__(spec)
        kwargs = {"timeout": spec.timeout_s, "max_retries": 4}
        if spec.api_key():
            kwargs["api_key"] = spec.api_key()
        if spec.base_url:
            kwargs["base_url"] = spec.base_url
        self.client = client or anthropic.AsyncAnthropic(**kwargs)

    def build_request(self, image: bytes, media_type: str, prompt: str) -> dict:
        p = self.spec.params
        req: dict = {
            "model": self.spec.model,
            "max_tokens": self.spec.max_output_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64(image)},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        output_config: dict = {}
        if self.spec.structured_output:
            output_config["format"] = {"type": "json_schema", "schema": OUTPUT_SCHEMA}
        if p.get("effort"):
            output_config["effort"] = p["effort"]
        if output_config:
            req["output_config"] = output_config
        if p.get("thinking"):
            req["thinking"] = p["thinking"]
        req.update(p.get("extra", {}))
        return req

    async def complete(self, image: bytes, media_type: str, prompt: str) -> ProviderResult:
        req = self.build_request(image, media_type, prompt)
        try:
            msg = await self.client.messages.create(**req)
        except (
            anthropic.BadRequestError,
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
            anthropic.NotFoundError,
        ) as e:
            raise ProviderError(f"{type(e).__name__}: {e.message}") from e

        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        u = msg.usage
        details = getattr(u, "output_tokens_details", None)
        cache_read = u.cache_read_input_tokens or 0
        cache_write = u.cache_creation_input_tokens or 0
        usage = Usage(
            # Anthropic's input_tokens excludes cache reads/writes; normalize to the total.
            input_tokens=u.input_tokens + cache_read + cache_write,
            output_tokens=u.output_tokens,
            reasoning_tokens=getattr(details, "thinking_tokens", 0) or 0,
            cached_input_tokens=cache_read,
        )
        return ProviderResult(
            text=text,
            usage=usage,
            stop_reason=msg.stop_reason,
            request_id=getattr(msg, "_request_id", None),
            refused=msg.stop_reason == "refusal",
            truncated=msg.stop_reason == "max_tokens",
            served_model=msg.model,
        )

    async def aclose(self) -> None:
        await self.client.close()
