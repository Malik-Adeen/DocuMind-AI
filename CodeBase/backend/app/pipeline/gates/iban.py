from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.pipeline.gates.base import GateResult, GateState

GATE_NAME = "iban_checksum"
FIELD_NAME = "iban"

_PK_IBAN = re.compile(r"PK[0-9]{2}[A-Z]{4}[0-9]{16}")
_AFFECTED = (FIELD_NAME,)
_LETTER_OFFSET = 55


def _stored_value(extraction: Mapping[str, Any]) -> str | None:
    fields = extraction.get("fields")
    if not isinstance(fields, Mapping):
        return None
    entry = fields.get(FIELD_NAME)
    if not isinstance(entry, Mapping):
        return None
    value = entry.get("value")
    return value if isinstance(value, str) else None


def _normalise(value: str) -> str:
    return "".join(value.split()).upper()


def _mod_97(iban: str) -> int:
    rearranged = iban[4:] + iban[:4]
    digits = "".join(
        str(ord(char) - _LETTER_OFFSET) if char.isalpha() else char for char in rearranged
    )
    return int(digits) % 97


def check_iban(extraction: Mapping[str, Any]) -> GateResult:
    raw = _stored_value(extraction)

    if raw is None or not raw.strip():
        return GateResult(
            name=GATE_NAME,
            state=GateState.FORMAT_ONLY,
            detail="iban field absent; no value to check",
            affected_fields=_AFFECTED,
        )

    candidate = _normalise(raw)

    if not _PK_IBAN.fullmatch(candidate):
        return GateResult(
            name=GATE_NAME,
            state=GateState.FAILED,
            detail=(
                "expected a 24-character PK IBAN "
                "(PK, 2 check digits, 4-letter bank code, 16 digits), "
                f"got {candidate!r}"
            ),
            affected_fields=_AFFECTED,
        )

    remainder = _mod_97(candidate)

    if remainder != 1:
        return GateResult(
            name=GATE_NAME,
            state=GateState.FAILED,
            detail=f"mod-97 checksum failed: remainder {remainder}, expected 1",
            affected_fields=_AFFECTED,
        )

    return GateResult(
        name=GATE_NAME,
        state=GateState.PASSED,
        detail="mod-97 checksum verified",
        affected_fields=_AFFECTED,
    )
