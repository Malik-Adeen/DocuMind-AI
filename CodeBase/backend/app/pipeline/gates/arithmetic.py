from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from app.pipeline.gates.base import GateResult, GateState

LINE_ITEM_GATE = "line_item_sum"
TOTALS_GATE = "arithmetic_reconciliation"

_MONEY = re.compile(r"-?[0-9]+\.[0-9]{2}")
_QUANTITY = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
_ZERO = Decimal("0.00")


class _MalformedAmountError(Exception):
    def __init__(self, field: str, raw: str) -> None:
        super().__init__(field)
        self.field = field
        self.raw = raw


def _raw(container: Mapping[str, Any], name: str) -> str | None:
    entry = container.get(name)
    if not isinstance(entry, Mapping):
        return None
    value = entry.get("value")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _parse(container: Mapping[str, Any], name: str, pattern: re.Pattern[str]) -> Decimal | None:
    raw = _raw(container, name)
    if raw is None:
        return None
    if not pattern.fullmatch(raw):
        raise _MalformedAmountError(name, raw)
    try:
        parsed = Decimal(raw)
    except InvalidOperation as exc:
        raise _MalformedAmountError(name, raw) from exc
    if not parsed.is_finite():
        raise _MalformedAmountError(name, raw)
    return parsed


def _money(container: Mapping[str, Any], name: str) -> Decimal | None:
    return _parse(container, name, _MONEY)


def _quantity(container: Mapping[str, Any], name: str) -> Decimal | None:
    return _parse(container, name, _QUANTITY)


def _fields(extraction: Mapping[str, Any]) -> Mapping[str, Any]:
    fields = extraction.get("fields")
    return fields if isinstance(fields, Mapping) else {}


def _line_items(extraction: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    items = extraction.get("line_items")
    if not isinstance(items, Sequence) or isinstance(items, str | bytes):
        return []
    return [item for item in items if isinstance(item, Mapping)]


def _malformed(gate: str, bad: _MalformedAmountError) -> GateResult:
    return GateResult(
        name=gate,
        state=GateState.FAILED,
        detail=f"{bad.field} is not a valid decimal amount: {bad.raw!r}",
        affected_fields=(bad.field,),
    )


def _absent(gate: str, missing: tuple[str, ...], what: str) -> GateResult:
    return GateResult(
        name=gate,
        state=GateState.FORMAT_ONLY,
        detail=f"{what} not computable: {', '.join(missing)} absent",
        affected_fields=missing,
    )


def _check_line_items(extraction: Mapping[str, Any]) -> GateResult:
    fields = _fields(extraction)
    items = _line_items(extraction)

    try:
        subtotal = _money(fields, "subtotal")
    except _MalformedAmountError as bad:
        return _malformed(LINE_ITEM_GATE, bad)

    if not items:
        return _absent(LINE_ITEM_GATE, ("line_items",), "line item sum")
    if subtotal is None:
        return _absent(LINE_ITEM_GATE, ("subtotal",), "line item sum")

    totals: list[Decimal] = []
    product_errors: list[str] = []
    affected: list[str] = []

    for index, item in enumerate(items):
        try:
            line_total = _money(item, "line_total")
            unit_price = _money(item, "unit_price")
            quantity = _quantity(item, "quantity")
        except _MalformedAmountError as bad:
            return GateResult(
                name=LINE_ITEM_GATE,
                state=GateState.FAILED,
                detail=(
                    f"line_items[{index}].{bad.field} is not a valid decimal amount: {bad.raw!r}"
                ),
                affected_fields=(f"line_items[{index}].{bad.field}",),
            )

        if line_total is None:
            return _absent(LINE_ITEM_GATE, (f"line_items[{index}].line_total",), "line item sum")

        totals.append(line_total)

        if unit_price is not None and quantity is not None:
            expected = unit_price * quantity
            if expected != line_total:
                product_errors.append(
                    f"line_items[{index}]: {unit_price} x {quantity} = {expected}, "
                    f"line_total is {line_total}"
                )
                affected.extend(
                    (
                        f"line_items[{index}].unit_price",
                        f"line_items[{index}].quantity",
                        f"line_items[{index}].line_total",
                    )
                )

    summed = sum(totals, _ZERO)
    sum_matches = summed == subtotal

    if product_errors or not sum_matches:
        details = list(product_errors)
        if not sum_matches:
            details.append(f"line items sum to {summed}, subtotal is {subtotal}")
            affected.extend(f"line_items[{i}].line_total" for i in range(len(items)))
            affected.append("subtotal")
        return GateResult(
            name=LINE_ITEM_GATE,
            state=GateState.FAILED,
            detail="; ".join(details),
            affected_fields=tuple(dict.fromkeys(affected)),
        )

    return GateResult(
        name=LINE_ITEM_GATE,
        state=GateState.PASSED,
        detail=f"{len(items)} line items sum to subtotal {subtotal}",
        affected_fields=("subtotal",),
    )


def _check_totals(extraction: Mapping[str, Any]) -> GateResult:
    fields = _fields(extraction)

    try:
        subtotal = _money(fields, "subtotal")
        tax = _money(fields, "tax")
        total = _money(fields, "total")
    except _MalformedAmountError as bad:
        return _malformed(TOTALS_GATE, bad)

    missing = tuple(
        name
        for name, value in (("subtotal", subtotal), ("tax", tax), ("total", total))
        if value is None
    )
    if missing:
        return _absent(TOTALS_GATE, missing, "subtotal + tax = total")

    assert subtotal is not None and tax is not None and total is not None
    computed = subtotal + tax

    if computed != total:
        return GateResult(
            name=TOTALS_GATE,
            state=GateState.FAILED,
            detail=f"subtotal {subtotal} + tax {tax} = {computed}, total is {total}",
            affected_fields=("subtotal", "tax", "total"),
        )

    return GateResult(
        name=TOTALS_GATE,
        state=GateState.PASSED,
        detail=f"subtotal {subtotal} + tax {tax} = total {total}",
        affected_fields=("subtotal", "tax", "total"),
    )


def _check_mrc_otc(extraction: Mapping[str, Any]) -> GateResult:
    fields = _fields(extraction)

    try:
        mrc = _money(fields, "mrc")
        otc = _money(fields, "otc")
    except _MalformedAmountError as bad:
        return _malformed(TOTALS_GATE, bad)

    present = tuple(name for name, value in (("mrc", mrc), ("otc", otc)) if value is not None)
    if not present:
        return _absent(TOTALS_GATE, ("mrc", "otc"), "mrc/otc reconciliation")

    return GateResult(
        name=TOTALS_GATE,
        state=GateState.FORMAT_ONLY,
        detail=(
            "mrc/otc to total relationship is undetermined: no specified rule exists to "
            "check them against subtotal or total, and no arithmetic identity holds in "
            "general — an invoice may bill otc plus one month of mrc, a contract may state "
            "mrc with no total, and multi-month billing satisfies neither. See ADR-005"
        ),
        affected_fields=present,
    )


def check_arithmetic(extraction: Mapping[str, Any]) -> tuple[GateResult, ...]:
    return (
        _check_line_items(extraction),
        _check_totals(extraction),
        _check_mrc_otc(extraction),
    )
