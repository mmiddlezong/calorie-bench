"""OpenAI-compatible Chat Completions endpoints (xAI, OpenRouter, and anything else that
speaks the /chat/completions dialect), via the official `openai` SDK with a base_url.

Supported `params` in models.yaml:
  reasoning_effort: passed as `reasoning_effort` (only for models that accept it)
  image_detail:     low | high | auto (default: high)
  extra_body:       dict sent as extra JSON body fields (e.g. OpenRouter `provider`
                    routing preferences or `reasoning` settings)
  extra:            dict merged into the request kwargs as-is
"""

from __future__ import annotations

import openai

from ..prompt import OUTPUT_SCHEMA, SCHEMA_NAME
from .base import Provider, ProviderError, ProviderResult, Usage, data_url

_FATAL = (openai.BadRequestError, openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError)


class OpenAIChatProvider(Provider):
    def __init__(self, spec, client: openai.AsyncOpenAI | None = None):
        super().__init__(spec)
        self.client = client or openai.AsyncOpenAI(
            api_key=spec.api_key(),
            base_url=spec.resolved_base_url(),
            timeout=spec.timeout_s,
            max_retries=4,
        )

    def build_request(self, image: bytes, media_type: str, prompt: str) -> dict:
        p = self.spec.params
        req: dict = {
            "model": self.spec.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url(image, media_type),
                                "detail": p.get("image_detail", "high"),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_completion_tokens": self.spec.max_output_tokens,
        }
        if self.spec.structured_output:
            req["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "schema": OUTPUT_SCHEMA, "strict": True},
            }
        if p.get("reasoning_effort"):
            req["reasoning_effort"] = p["reasoning_effort"]
        if p.get("extra_body"):
            req["extra_body"] = p["extra_body"]
        req.update(p.get("extra", {}))
        return req

    async def complete(self, image: bytes, media_type: str, prompt: str) -> ProviderResult:
        req = self.build_request(image, media_type, prompt)
        try:
            resp = await self.client.chat.completions.create(**req)
        except _FATAL as e:
            raise ProviderError(f"{type(e).__name__}: {e.message}") from e

        if not resp.choices:
            raise RuntimeError(f"No choices in response: {resp.model_dump_json()[:500]}")
        choice = resp.choices[0]
        msg = choice.message
        finish = choice.finish_reason
        refused = bool(getattr(msg, "refusal", None)) or finish == "content_filter"

        u = resp.usage
        usage = Usage()
        provider_cost = None
        if u is not None:
            out_details = getattr(u, "completion_tokens_details", None)
            in_details = getattr(u, "prompt_tokens_details", None)
            usage = Usage(
                input_tokens=u.prompt_tokens or 0,
                output_tokens=u.completion_tokens or 0,
                reasoning_tokens=getattr(out_details, "reasoning_tokens", 0) or 0,
                cached_input_tokens=getattr(in_details, "cached_tokens", 0) or 0,
            )
            # OpenRouter reports the actual charge in usage.cost (USD).
            extra = getattr(u, "model_extra", None) or {}
            if isinstance(extra.get("cost"), (int, float)):
                provider_cost = float(extra["cost"])
            # Some OpenAI-compatible servers (e.g. xAI) report reasoning tokens separately
            # from completion_tokens; count them as billable output if so.
            if usage.reasoning_tokens and usage.output_tokens < usage.reasoning_tokens:
                usage.output_tokens += usage.reasoning_tokens

        return ProviderResult(
            text=msg.content,
            usage=usage,
            stop_reason=finish,
            request_id=getattr(resp, "_request_id", None) or resp.id,
            refused=refused,
            truncated=finish == "length",
            provider_cost_usd=provider_cost,
            served_model=resp.model,
        )

    async def aclose(self) -> None:
        await self.client.close()
