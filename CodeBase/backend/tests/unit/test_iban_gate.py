from __future__ import annotations

from typing import Any

import pytest

from app.pipeline.gates.base import GateState
from app.pipeline.gates.iban import GATE_NAME, check_iban

VALID = "PK36SCBL0000001123456702"
VALID_OTHER = "PK24SCBL0000001171495101"
BAD_CHECKSUM = "PK70BANK0000001234567890"
NON_PK = "GB82WEST12345698765432"


def extraction(value: Any) -> dict[str, Any]:
    return {
        "document_id": "11111111-1111-1111-1111-111111111111",
        "fields": {
            "iban": {
                "value": value,
                "confidence": 0.91,
                "verified": False,
                "source": {"origin": "ocr_latin", "page": 1},
            }
        },
    }


@pytest.mark.parametrize("value", [VALID, VALID_OTHER])
def test_valid_pk_iban_passes(value: str) -> None:
    result = check_iban(extraction(value))
    assert result.state is GateState.PASSED
    assert result.verifies is True
    assert result.name == GATE_NAME
    assert result.affected_fields == ("iban",)


def test_valid_format_but_checksum_fails() -> None:
    result = check_iban(extraction(BAD_CHECKSUM))
    assert result.state is GateState.FAILED
    assert result.verifies is False
    assert "mod-97" in result.detail


@pytest.mark.parametrize(
    "value",
    [
        "PK36SCBL000000112345670",
        "PK36SCBL00000011234567021",
        "PK36SCBL",
        "",
    ],
)
def test_wrong_length_fails(value: str) -> None:
    result = check_iban(extraction(value))
    assert result.state is not GateState.PASSED
    assert result.verifies is False


def test_lowercase_is_normalised_and_passes() -> None:
    result = check_iban(extraction(VALID.lower()))
    assert result.state is GateState.PASSED


def test_embedded_spaces_are_normalised_and_passes() -> None:
    spaced = "PK36 SCBL 0000 0011 2345 6702"
    result = check_iban(extraction(spaced))
    assert result.state is GateState.PASSED


def test_lowercase_with_spaces_passes() -> None:
    result = check_iban(extraction("  pk36 scbl 0000 0011 2345 6702  "))
    assert result.state is GateState.PASSED


def test_non_pk_country_code_fails() -> None:
    result = check_iban(extraction(NON_PK))
    assert result.state is GateState.FAILED
    assert result.verifies is False


def test_absent_field_is_format_only() -> None:
    result = check_iban({"document_id": "x", "fields": {}})
    assert result.state is GateState.FORMAT_ONLY
    assert result.verifies is False
    assert "absent" in result.detail


def test_absent_fields_block_is_format_only() -> None:
    result = check_iban({"document_id": "x"})
    assert result.state is GateState.FORMAT_ONLY
    assert "absent" in result.detail


def test_null_field_is_format_only() -> None:
    result = check_iban(extraction(None))
    assert result.state is GateState.FORMAT_ONLY
    assert result.verifies is False
    assert "absent" in result.detail


def test_whitespace_only_value_is_format_only() -> None:
    result = check_iban(extraction("   "))
    assert result.state is GateState.FORMAT_ONLY


def test_only_passed_can_verify() -> None:
    states = [
        check_iban(extraction(VALID)),
        check_iban(extraction(BAD_CHECKSUM)),
        check_iban(extraction(NON_PK)),
        check_iban(extraction(None)),
    ]
    assert [r.verifies for r in states] == [True, False, False, False]


def test_gate_result_is_immutable() -> None:
    result = check_iban(extraction(VALID))
    with pytest.raises(AttributeError):
        result.state = GateState.FAILED  # type: ignore[misc]


def test_state_serialises_to_schema_values() -> None:
    assert GateState.PASSED == "passed"
    assert GateState.FAILED == "failed"
    assert GateState.FORMAT_ONLY == "format_only"
