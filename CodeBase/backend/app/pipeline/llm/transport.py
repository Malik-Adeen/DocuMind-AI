from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

CHAT_COMPLETIONS_PATH = "chat/completions"


class HostedLLMError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class HostedChatTransport:
    client: httpx.Client
    model: str
    temperature: float = 0.0
    max_tokens: int = 2000
    seed: int | None = None
    provider_order: tuple[str, ...] | None = None

    def _request_body(self, prompt: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.seed is not None:
            body["seed"] = self.seed
        if self.provider_order is not None:
            body["provider"] = {"order": list(self.provider_order), "allow_fallbacks": False}
        return body

    def complete_full(self, prompt: str) -> tuple[str, dict[str, Any]]:
        try:
            response = self.client.post(CHAT_COMPLETIONS_PATH, json=self._request_body(prompt))
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HostedLLMError(
                f"hosted LLM endpoint returned {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise HostedLLMError(f"hosted LLM request failed: {exc}") from exc

        body = response.json()
        try:
            content = str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise HostedLLMError(f"unexpected hosted LLM response shape: {body!r}") from exc
        return content, body

    def __call__(self, prompt: str) -> str:
        content, _ = self.complete_full(prompt)
        return content
