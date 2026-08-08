from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

DEFAULT_MAX_RETRIES = 1


class RepairExhaustedError(RuntimeError):
    def __init__(self, attempts: int, last_error: str) -> None:
        super().__init__(f"LLM output was still invalid after {attempts} attempt(s): {last_error}")
        self.attempts = attempts
        self.last_error = last_error


def build_repair_prompt(original_prompt: str, bad_output: str, error: str) -> str:
    return (
        f"{original_prompt}\n\n"
        "Your previous response could not be used:\n"
        f"{error}\n\n"
        "Previous response:\n"
        f"{bad_output}\n\n"
        "Return ONLY corrected JSON matching the schema above. No prose, no markdown fences."
    )


def complete_with_repair(
    complete: Callable[[str], str],
    prompt: str,
    *,
    validate: Callable[[dict[str, Any]], None],
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict[str, Any]:
    attempt_prompt = prompt
    last_error = "unknown error"

    for _attempt in range(max_retries + 1):
        raw = complete(attempt_prompt)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            last_error = f"invalid JSON: {exc}"
            attempt_prompt = build_repair_prompt(prompt, raw, last_error)
            continue
        if not isinstance(parsed, dict):
            last_error = "output JSON was not an object"
            attempt_prompt = build_repair_prompt(prompt, raw, last_error)
            continue
        try:
            validate(parsed)
        except Exception as exc:
            last_error = str(exc)
            attempt_prompt = build_repair_prompt(prompt, raw, last_error)
            continue
        return parsed

    raise RepairExhaustedError(max_retries + 1, last_error)
