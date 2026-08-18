from __future__ import annotations

from typing import Any

from app.pipeline.gates.arithmetic import (
    LINE_ITEM_GATE,
    TOTALS_GATE,
    check_arithmetic,
)
from app.pipeline.gates.base import GateState


def money(value: str | None) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": 0.9,
        "verified": False,
        "source": {"origin": "llm_inferred", "page": 1},
    }


def item(quantity: str | None, unit_price: str | None, line_total: str | None) -> dict[str, Any]:
    return {
        "description": money("Fibre link"),
        "quantity": money(quantity),
        "unit_price": money(unit_price),
        "line_total": money(line_total),
    }


def build(
    *,
    items: list[dict[str, Any]] | None = None,
    subtotal: str | None = None,
    tax: str | None = None,
    total: str | None = None,
    mrc: str | None = None,
    otc: str | None = None,
    omit: tuple[str, ...] = (),
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "subtotal": money(subtotal),
        "tax": money(tax),
        "total": money(total),
        "mrc": money(mrc),
        "otc": money(otc),
    }
    for name in omit:
        fields.pop(name, None)
    extraction: dict[str, Any] = {"document_id": "doc-1", "fields": fields}
    if items is not None:
        extraction["line_items"] = items
    return extraction


CLEAN = build(
    items=[item("2", "10000.00", "20000.00"), item("1", "5000.00", "5000.00")],
    subtotal="25000.00",
    tax="4250.00",
    total="29250.00",
    mrc="20000.00",
    otc="5000.00",
)


def by_name(results: tuple[Any, ...]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for result in results:
        grouped.setdefault(result.name, []).append(result)
    return grouped


def test_clean_invoice_arithmetic_passes_mrc_otc_stays_undetermined() -> None:
    results = check_arithmetic(CLEAN)
    assert len(results) == 3
    assert [r.state for r in results] == [
        GateState.PASSED,
        GateState.PASSED,
        GateState.FORMAT_ONLY,
    ]


def test_off_by_one_paisa_subtotal_fails_line_item_sum() -> None:
    results = check_arithmetic(
        build(
            items=[item("2", "10000.00", "20000.00"), item("1", "5000.00", "5000.00")],
            subtotal="25000.01",
            tax="4250.00",
            total="29250.01",
        )
    )
    line_items = by_name(results)[LINE_ITEM_GATE][0]
    assert line_items.state is GateState.FAILED
    assert "25000.00" in line_items.detail
    assert "subtotal" in line_items.affected_fields


def test_tax_mismatch_fails_totals_only() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "25000.00", "25000.00")],
            subtotal="25000.00",
            tax="4000.00",
            total="29250.00",
        )
    )
    grouped = by_name(results)
    assert grouped[LINE_ITEM_GATE][0].state is GateState.PASSED
    totals = grouped[TOTALS_GATE][0]
    assert totals.state is GateState.FAILED
    assert totals.affected_fields == ("subtotal", "tax", "total")


def test_missing_tax_is_format_only_not_failed() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "25000.00", "25000.00")],
            subtotal="25000.00",
            total="25000.00",
            omit=("tax",),
        )
    )
    grouped = by_name(results)
    totals = grouped[TOTALS_GATE][0]
    assert totals.state is GateState.FORMAT_ONLY
    assert totals.verifies is False
    assert "tax" in totals.detail
    assert grouped[LINE_ITEM_GATE][0].state is GateState.PASSED


def test_missing_line_items_is_format_only() -> None:
    results = check_arithmetic(build(subtotal="100.00", tax="17.00", total="117.00"))
    grouped = by_name(results)
    line_items = grouped[LINE_ITEM_GATE][0]
    assert line_items.state is GateState.FORMAT_ONLY
    assert "line_items" in line_items.detail
    assert grouped[TOTALS_GATE][0].state is GateState.PASSED


def test_empty_line_items_with_a_total_still_checks_totals() -> None:
    results = check_arithmetic(build(items=[], subtotal="100.00", tax="17.00", total="117.00"))
    grouped = by_name(results)
    assert grouped[LINE_ITEM_GATE][0].state is GateState.FORMAT_ONLY
    assert grouped[TOTALS_GATE][0].state is GateState.PASSED


def test_negative_amounts_credit_note_passes() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "-5000.00", "-5000.00")],
            subtotal="-5000.00",
            tax="-850.00",
            total="-5850.00",
            mrc="-5000.00",
            otc="0.00",
        )
    )
    assert [r.state for r in results] == [
        GateState.PASSED,
        GateState.PASSED,
        GateState.FORMAT_ONLY,
    ]


def test_credit_note_with_wrong_total_fails() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "-5000.00", "-5000.00")],
            subtotal="-5000.00",
            tax="-850.00",
            total="-4150.00",
            mrc="-5000.00",
            otc="0.00",
        )
    )
    totals = by_name(results)[TOTALS_GATE][0]
    assert totals.state is GateState.FAILED
    assert "-5850.00" in totals.detail
    assert totals.affected_fields == ("subtotal", "tax", "total")


def test_credit_note_with_wrong_line_item_sum_fails() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "-5000.00", "-5000.00"), item("1", "-1000.00", "-1000.00")],
            subtotal="-5000.00",
            tax="0.00",
            total="-5000.00",
        )
    )
    line_items = by_name(results)[LINE_ITEM_GATE][0]
    assert line_items.state is GateState.FAILED
    assert "-6000.00" in line_items.detail


def test_sign_error_on_credit_note_is_caught() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "-5000.00", "-5000.00")],
            subtotal="-5000.00",
            tax="-850.00",
            total="5850.00",
        )
    )
    totals = by_name(results)[TOTALS_GATE][0]
    assert totals.state is GateState.FAILED


def test_line_item_product_mismatch_fails() -> None:
    results = check_arithmetic(build(items=[item("3", "10.00", "35.00")], subtotal="35.00"))
    line_items = by_name(results)[LINE_ITEM_GATE][0]
    assert line_items.state is GateState.FAILED
    assert "30.00" in line_items.detail
    assert line_items.affected_fields == (
        "line_items[0].unit_price",
        "line_items[0].quantity",
        "line_items[0].line_total",
    )


def test_product_mismatch_reported_even_when_sum_matches() -> None:
    results = check_arithmetic(build(items=[item("3", "10.00", "35.00")], subtotal="35.00"))
    line_items = by_name(results)[LINE_ITEM_GATE][0]
    assert line_items.state is GateState.FAILED
    assert "subtotal" not in line_items.affected_fields


def test_mrc_otc_never_asserts_a_relationship_to_subtotal() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "25000.00", "25000.00")],
            subtotal="25000.00",
            tax="0.00",
            total="25000.00",
            mrc="20000.00",
            otc="1000.00",
        )
    )
    mrc_otc = by_name(results)[TOTALS_GATE][1]
    assert mrc_otc.state is GateState.FORMAT_ONLY
    assert mrc_otc.verifies is False
    assert "undetermined" in mrc_otc.detail


def test_mrc_otc_that_happens_to_sum_still_does_not_verify() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "25000.00", "25000.00")],
            subtotal="25000.00",
            tax="0.00",
            total="25000.00",
            mrc="20000.00",
            otc="5000.00",
        )
    )
    mrc_otc = by_name(results)[TOTALS_GATE][1]
    assert mrc_otc.state is GateState.FORMAT_ONLY
    assert mrc_otc.verifies is False


def test_multi_month_billing_does_not_fail_mrc_otc() -> None:
    results = check_arithmetic(
        build(
            items=[
                item("3", "20000.00", "60000.00"),
                item("1", "5000.00", "5000.00"),
            ],
            subtotal="65000.00",
            tax="0.00",
            total="65000.00",
            mrc="20000.00",
            otc="5000.00",
        )
    )
    grouped = by_name(results)
    assert grouped[LINE_ITEM_GATE][0].state is GateState.PASSED
    assert grouped[TOTALS_GATE][0].state is GateState.PASSED
    assert grouped[TOTALS_GATE][1].state is GateState.FORMAT_ONLY


def test_mrc_without_otc_is_format_only() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "25000.00", "25000.00")],
            subtotal="25000.00",
            tax="0.00",
            total="25000.00",
            mrc="25000.00",
            omit=("otc",),
        )
    )
    mrc_otc = by_name(results)[TOTALS_GATE][1]
    assert mrc_otc.state is GateState.FORMAT_ONLY
    assert mrc_otc.affected_fields == ("mrc",)


def test_partial_data_reports_per_check_not_one_verdict() -> None:
    results = check_arithmetic(
        build(items=[item("1", "100.00", "100.00")], subtotal="100.00", omit=("tax",))
    )
    states = [r.state for r in results]
    assert states == [GateState.PASSED, GateState.FORMAT_ONLY, GateState.FORMAT_ONLY]


def test_decimal_not_float() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "0.10", "0.10"), item("1", "0.20", "0.20")],
            subtotal="0.30",
            tax="0.00",
            total="0.30",
        )
    )
    grouped = by_name(results)
    assert grouped[LINE_ITEM_GATE][0].state is GateState.PASSED
    assert grouped[TOTALS_GATE][0].state is GateState.PASSED


def test_malformed_amount_fails_rather_than_being_skipped() -> None:
    results = check_arithmetic(
        build(items=[item("1", "100.00", "100.00")], subtotal="4.5e4", tax="0.00")
    )
    line_items = by_name(results)[LINE_ITEM_GATE][0]
    assert line_items.state is GateState.FAILED
    assert "4.5e4" in line_items.detail
    totals_named = by_name(results)[TOTALS_GATE]
    assert any("tax" in r.affected_fields for r in totals_named)


def test_malformed_subtotal_does_not_orphan_tax_and_total() -> None:
    results = check_arithmetic(build(subtotal="533.0", tax="26.65", total="559.65"))
    totals_named = by_name(results)[TOTALS_GATE]
    subtotal_verdict = next(r for r in totals_named if r.affected_fields == ("subtotal",))
    assert subtotal_verdict.state is GateState.FAILED
    assert "533.0" in subtotal_verdict.detail
    not_computable = next(r for r in totals_named if r is not subtotal_verdict)
    assert not_computable.state is GateState.FORMAT_ONLY
    assert set(not_computable.affected_fields) == {"tax", "total"}


def test_malformed_tax_does_not_orphan_subtotal_and_total() -> None:
    results = check_arithmetic(build(subtotal="533.00", tax="26.6", total="559.65"))
    totals_named = by_name(results)[TOTALS_GATE]
    tax_verdict = next(r for r in totals_named if r.affected_fields == ("tax",))
    assert tax_verdict.state is GateState.FAILED
    assert "26.6" in tax_verdict.detail
    not_computable = next(r for r in totals_named if r is not tax_verdict)
    assert not_computable.state is GateState.FORMAT_ONLY
    assert set(not_computable.affected_fields) == {"subtotal", "total"}


def test_two_malformed_totals_fields_are_both_reported() -> None:
    results = check_arithmetic(build(subtotal="533.0", tax="26.6", total="559.65"))
    totals_named = by_name(results)[TOTALS_GATE]
    malformed = {r.affected_fields[0] for r in totals_named if r.state is GateState.FAILED}
    assert malformed == {"subtotal", "tax"}
    not_computable = next(r for r in totals_named if r.state is GateState.FORMAT_ONLY)
    assert not_computable.affected_fields == ("total",)


def test_malformed_mrc_does_not_orphan_otc() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "25000.00", "25000.00")],
            subtotal="25000.00",
            tax="0.00",
            total="25000.00",
            mrc="2e4",
            otc="5000.00",
        )
    )
    totals_named = by_name(results)[TOTALS_GATE]
    mrc_verdict = next(r for r in totals_named if r.affected_fields == ("mrc",))
    assert mrc_verdict.state is GateState.FAILED
    otc_verdict = next(
        r for r in totals_named if "otc" in r.affected_fields and r is not mrc_verdict
    )
    assert otc_verdict.state is GateState.FORMAT_ONLY
    assert otc_verdict.affected_fields == ("otc",)


def test_malformed_otc_does_not_orphan_mrc() -> None:
    results = check_arithmetic(
        build(
            items=[item("1", "25000.00", "25000.00")],
            subtotal="25000.00",
            tax="0.00",
            total="25000.00",
            mrc="20000.00",
            otc="5e3",
        )
    )
    totals_named = by_name(results)[TOTALS_GATE]
    otc_verdict = next(r for r in totals_named if r.affected_fields == ("otc",))
    assert otc_verdict.state is GateState.FAILED
    mrc_verdict = next(
        r for r in totals_named if "mrc" in r.affected_fields and r is not otc_verdict
    )
    assert mrc_verdict.state is GateState.FORMAT_ONLY
    assert mrc_verdict.affected_fields == ("mrc",)


def test_line_item_two_malformed_fields_in_one_item_are_both_reported() -> None:
    results = check_arithmetic(build(items=[item("3.5.5", "10.0", "100.00")], subtotal="100.00"))
    line_items = by_name(results)[LINE_ITEM_GATE]
    malformed = {r.affected_fields[0] for r in line_items if r.state is GateState.FAILED}
    assert malformed == {"line_items[0].quantity", "line_items[0].unit_price"}
    summary = next(r for r in line_items if r.state is not GateState.FAILED)
    assert summary.state is GateState.PASSED
    assert summary.affected_fields == ("subtotal",)


def test_malformed_totals_fields_do_not_shift_mrc_otc_result_position() -> None:
    results = check_arithmetic(
        build(subtotal="533.0", tax="26.6", total="559.65", mrc="20000.00", otc="5000.00")
    )
    totals_named = by_name(results)[TOTALS_GATE]
    assert len(totals_named) == 4
    mrc_otc = next(r for r in totals_named if set(r.affected_fields) == {"mrc", "otc"})
    assert mrc_otc.state is GateState.FORMAT_ONLY
    assert not mrc_otc.verifies
    assert "undetermined" in mrc_otc.detail
    malformed = {r.affected_fields[0] for r in totals_named if r.state is GateState.FAILED}
    assert malformed == {"subtotal", "tax"}
    not_computable = next(
        r for r in totals_named if r.state is GateState.FORMAT_ONLY and r is not mrc_otc
    )
    assert not_computable.affected_fields == ("total",)


def test_null_valued_fields_are_absent_not_malformed() -> None:
    results = check_arithmetic(
        build(items=[item("1", "100.00", "100.00")], subtotal="100.00", tax=None)
    )
    totals = by_name(results)[TOTALS_GATE][0]
    assert totals.state is GateState.FORMAT_ONLY


def test_format_only_never_verifies() -> None:
    results = check_arithmetic(build())
    assert all(r.state is GateState.FORMAT_ONLY for r in results)
    assert not any(r.verifies for r in results)
