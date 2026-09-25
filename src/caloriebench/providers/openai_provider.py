"""OpenAI Responses API (official `openai` SDK). Also usable for any other endpoint that
implements the Responses API (set `base_url` / `api_key_env` in models.yaml).

Supported `params` in models.yaml:
  reasoning_effort: none | minimal | low | medium | high | xhigh  -> reasoning.effort
  verbosity:        low | medium | high                             -> text.verbosity
  image_detail:     low | high | auto | original (default: high)
  extra:            dict merged into the request as-is
"""

from __future__ import annotations

import openai

from ..prompt import OUTPUT_SCHEMA, SCHEMA_NAME
from .base import Provider, ProviderError, ProviderResult, Usage, data_url

_FATAL = (openai.BadRequestError, openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError)


class OpenAIResponsesProvider(Provider):
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
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": data_url(image, media_type),
                            "detail": p.get("image_detail", "high"),
                        },
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
            "max_output_tokens": self.spec.max_output_tokens,
            "store": False,
        }
        text: dict = {}
        if self.spec.structured_output:
            text["format"] = {
                "type": "json_schema",
                "name": SCHEMA_NAME,
                "schema": OUTPUT_SCHEMA,
                "strict": True,
            }
        if p.get("verbosity"):
            text["verbosity"] = p["verbosity"]
        if text:
            req["text"] = text
        if p.get("reasoning_effort"):
            req["reasoning"] = {"effort": p["reasoning_effort"]}
        req.update(p.get("extra", {}))
        return req

    async def complete(self, image: bytes, media_type: str, prompt: str) -> ProviderResult:
        req = self.build_request(image, media_type, prompt)
        try:
            resp = await self.client.responses.create(**req)
        except _FATAL as e:
            raise ProviderError(f"{type(e).__name__}: {e.message}") from e

        refused = False
        for item in resp.output or []:
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", None) == "refusal":
                    refused = True
        incomplete = getattr(resp, "incomplete_details", None)
        reason = getattr(incomplete, "reason", None) if incomplete else None
        if reason == "content_filter":
            refused = True

        u = resp.usage
        usage = Usage()
        if u is not None:
            out_details = getattr(u, "output_tokens_details", None)
            in_details = getattr(u, "input_tokens_details", None)
            usage = Usage(
                input_tokens=u.input_tokens or 0,
                output_tokens=u.output_tokens or 0,
                reasoning_tokens=getattr(out_details, "reasoning_tokens", 0) or 0,
                cached_input_tokens=getattr(in_details, "cached_tokens", 0) or 0,
            )
        return ProviderResult(
            text=resp.output_text,
            usage=usage,
            stop_reason=reason or resp.status,
            request_id=getattr(resp, "_request_id", None),
            refused=refused,
            truncated=reason == "max_output_tokens",
            served_model=resp.model,
        )

    async def aclose(self) -> None:
        await self.client.close()
