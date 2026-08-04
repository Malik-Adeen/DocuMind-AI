from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GateState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    FORMAT_ONLY = "format_only"


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    state: GateState
    detail: str
    affected_fields: tuple[str, ...] = ()

    @property
    def verifies(self) -> bool:
        return self.state is GateState.PASSED
