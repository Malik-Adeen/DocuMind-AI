from __future__ import annotations

from typing import Any

import pytest

from app.pipeline.llm.repair import RepairExhaustedError, complete_with_repair


class CountingTransport:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        index = min(len(self.prompts) - 1, len(self.responses) - 1)
        return self.responses[index]


def no_op_validate(parsed: dict[str, Any]) -> None:
    return None


def require_field(name: str) -> Any:
    def validate(parsed: dict[str, Any]) -> None:
        if name not in parsed:
            raise ValueError(f"missing required key {name!r}")

    return validate


def test_succeeds_on_first_attempt_when_valid() -> None:
    transport = CountingTransport(['{"ok": true}'])

    result = complete_with_repair(transport, "extract this", validate=no_op_validate)

    assert result == {"ok": True}
    assert transport.prompts == ["extract this"]


def test_retries_once_on_invalid_json_then_succeeds() -> None:
    transport = CountingTransport(["not json", '{"ok": true}'])

    result = complete_with_repair(transport, "extract this", validate=no_op_validate)

    assert result == {"ok": True}
    assert len(transport.prompts) == 2


def test_retries_once_on_validation_failure_then_succeeds() -> None:
    transport = CountingTransport(['{"nope": 1}', '{"fields": {}}'])

    result = complete_with_repair(transport, "extract this", validate=require_field("fields"))

    assert result == {"fields": {}}
    assert len(transport.prompts) == 2


def test_raises_repair_exhausted_after_max_retries() -> None:
    transport = CountingTransport(["still not json", "still not json"])

    with pytest.raises(RepairExhaustedError) as caught:
        complete_with_repair(transport, "extract this", validate=no_op_validate)

    assert caught.value.attempts == 2
    assert len(transport.prompts) == 2


def test_default_max_retries_is_one_so_at_most_two_calls_happen() -> None:
    transport = CountingTransport(["bad"] * 5)

    with pytest.raises(RepairExhaustedError):
        complete_with_repair(transport, "extract this", validate=no_op_validate)

    assert len(transport.prompts) == 2


def test_max_retries_is_configurable() -> None:
    transport = CountingTransport(["bad"] * 5)

    with pytest.raises(RepairExhaustedError) as caught:
        complete_with_repair(transport, "extract this", validate=no_op_validate, max_retries=3)

    assert caught.value.attempts == 4
    assert len(transport.prompts) == 4


def test_transport_errors_propagate_immediately_without_retry() -> None:
    def raising_transport(prompt: str) -> str:
        raise RuntimeError("INV-6: refused")

    with pytest.raises(RuntimeError, match="INV-6"):
        complete_with_repair(raising_transport, "extract this", validate=no_op_validate)


def test_repair_prompt_carries_the_error_and_the_bad_output() -> None:
    transport = CountingTransport(["not json at all", '{"ok": true}'])

    complete_with_repair(transport, "extract this", validate=no_op_validate)

    first, second = transport.prompts
    assert first == "extract this"
    assert second != first
    assert "not json at all" in second
    assert "extract this" in second
