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


def _malformed(gate: str, field: str, raw: str) -> GateResult:
    return GateResult(
        name=gate,
        state=GateState.FAILED,
        detail=f"{field} is not a valid decimal amount: {raw!r}",
        affected_fields=(field,),
    )


def _absent(gate: str, missing: tuple[str, ...], what: str) -> GateResult:
    return GateResult(
        name=gate,
        state=GateState.FORMAT_ONLY,
        detail=f"{what} not computable: {', '.join(missing)} absent",
        affected_fields=missing,
    )


def _parse_money_fields(
    container: Mapping[str, Any], names: Sequence[str], *, gate: str
) -> tuple[dict[str, Decimal], list[GateResult]]:
    clean: dict[str, Decimal] = {}
    malformed: list[GateResult] = []
    for name in names:
        try:
            value = _money(container, name)
        except _MalformedAmountError as bad:
            malformed.append(_malformed(gate, bad.field, bad.raw))
            continue
        if value is not None:
            clean[name] = value
    return clean, malformed


def _parse_line_item_fields(
    item: Mapping[str, Any], index: int
) -> tuple[dict[str, Decimal], list[GateResult]]:
    clean: dict[str, Decimal] = {}
    malformed: list[GateResult] = []
    for name, parser in (("line_total", _money), ("unit_price", _money), ("quantity", _quantity)):
        try:
            value = parser(item, name)
        except _MalformedAmountError as bad:
            malformed.append(
                _malformed(LINE_ITEM_GATE, f"line_items[{index}].{bad.field}", bad.raw)
            )
            continue
        if value is not None:
            clean[name] = value
    return clean, malformed


def _check_line_items(extraction: Mapping[str, Any]) -> tuple[GateResult, ...]:
    fields = _fields(extraction)
    items = _line_items(extraction)

    subtotal_clean, subtotal_malformed = _parse_money_fields(
        fields, ("subtotal",), gate=LINE_ITEM_GATE
    )
    subtotal = subtotal_clean.get("subtotal")
    results: list[GateResult] = list(subtotal_malformed)

    if not items:
        results.append(_absent(LINE_ITEM_GATE, ("line_items",), "line item sum"))
        return tuple(results)

    sum_computable = subtotal is not None
    not_computable: list[str] = []
    if subtotal is None and not subtotal_malformed:
        not_computable.append("subtotal")

    totals: list[Decimal] = []
    product_errors: list[str] = []
    affected: list[str] = []

    for index, item in enumerate(items):
        item_clean, item_malformed = _parse_line_item_fields(item, index)
        item_malformed_names = {
            result.affected_fields[0].rsplit(".", 1)[-1] for result in item_malformed
        }
        results.extend(item_malformed)

        line_total = item_clean.get("line_total")
        if line_total is None:
            sum_computable = False
            if "line_total" not in item_malformed_names:
                not_computable.append(f"line_items[{index}].line_total")
            continue

        totals.append(line_total)

        unit_price = item_clean.get("unit_price")
        quantity = item_clean.get("quantity")
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

    if not sum_computable:
        results.append(_absent(LINE_ITEM_GATE, tuple(not_computable), "line item sum"))
        return tuple(results)

    assert subtotal is not None
    summed = sum(totals, _ZERO)
    sum_matches = summed == subtotal

    if product_errors or not sum_matches:
        details = list(product_errors)
        if not sum_matches:
            details.append(f"line items sum to {summed}, subtotal is {subtotal}")
            affected.extend(f"line_items[{i}].line_total" for i in range(len(items)))
            affected.append("subtotal")
        results.append(
            GateResult(
                name=LINE_ITEM_GATE,
                state=GateState.FAILED,
                detail="; ".join(details),
                affected_fields=tuple(dict.fromkeys(affected)),
            )
        )
        return tuple(results)

    results.append(
        GateResult(
            name=LINE_ITEM_GATE,
            state=GateState.PASSED,
            detail=f"{len(items)} line items sum to subtotal {subtotal}",
            affected_fields=("subtotal",),
        )
    )
    return tuple(results)


def _check_totals(extraction: Mapping[str, Any]) -> tuple[GateResult, ...]:
    fields = _fields(extraction)
    clean, malformed = _parse_money_fields(fields, ("subtotal", "tax", "total"), gate=TOTALS_GATE)
    results: list[GateResult] = list(malformed)

    malformed_names = {result.affected_fields[0] for result in malformed}
    missing = tuple(
        name
        for name in ("subtotal", "tax", "total")
        if name not in clean and name not in malformed_names
    )

    if missing or malformed_names:
        still_needs_verdict = tuple(
            name for name in ("subtotal", "tax", "total") if name not in malformed_names
        )
        if still_needs_verdict:
            reasons = []
            if missing:
                reasons.append(f"{', '.join(missing)} absent")
            if malformed_names:
                reasons.append(f"{', '.join(sorted(malformed_names))} malformed")
            results.append(
                GateResult(
                    name=TOTALS_GATE,
                    state=GateState.FORMAT_ONLY,
                    detail=(f"subtotal + tax = total not computable: {'; '.join(reasons)}"),
                    affected_fields=still_needs_verdict,
                )
            )
        return tuple(results)

    subtotal, tax, total = clean["subtotal"], clean["tax"], clean["total"]
    computed = subtotal + tax

    if computed != total:
        results.append(
            GateResult(
                name=TOTALS_GATE,
                state=GateState.FAILED,
                detail=f"subtotal {subtotal} + tax {tax} = {computed}, total is {total}",
                affected_fields=("subtotal", "tax", "total"),
            )
        )
        return tuple(results)

    results.append(
        GateResult(
            name=TOTALS_GATE,
            state=GateState.PASSED,
            detail=f"subtotal {subtotal} + tax {tax} = total {total}",
            affected_fields=("subtotal", "tax", "total"),
        )
    )
    return tuple(results)


def _check_mrc_otc(extraction: Mapping[str, Any]) -> tuple[GateResult, ...]:
    fields = _fields(extraction)
    clean, malformed = _parse_money_fields(fields, ("mrc", "otc"), gate=TOTALS_GATE)
    results: list[GateResult] = list(malformed)

    present = tuple(name for name in ("mrc", "otc") if name in clean)
    if not present:
        if not malformed:
            results.append(_absent(TOTALS_GATE, ("mrc", "otc"), "mrc/otc reconciliation"))
        return tuple(results)

    results.append(
        GateResult(
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
    )
    return tuple(results)


def check_arithmetic(extraction: Mapping[str, Any]) -> tuple[GateResult, ...]:
    return (
        *_check_line_items(extraction),
        *_check_totals(extraction),
        *_check_mrc_otc(extraction),
    )
