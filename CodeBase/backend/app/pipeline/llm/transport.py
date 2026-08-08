from __future__ import annotations

from dataclasses import dataclass

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

    def __call__(self, prompt: str) -> str:
        try:
            response = self.client.post(
                CHAT_COMPLETIONS_PATH,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                },
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise HostedLLMError(
                f"hosted LLM endpoint returned {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise HostedLLMError(f"hosted LLM request failed: {exc}") from exc

        body = response.json()
        try:
            return str(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise HostedLLMError(f"unexpected hosted LLM response shape: {body!r}") from exc
