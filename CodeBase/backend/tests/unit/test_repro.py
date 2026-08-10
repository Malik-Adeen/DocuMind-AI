from __future__ import annotations

from evals.repro import ABSENT, INVALID_RESPONSE, render_table, summarize_all, summarize_field


def response(**fields: object) -> dict[str, object]:
    return {"fields": {name: {"value": value} for name, value in fields.items()}}


def test_all_identical_values_give_distinct_one_and_modal_rate_one() -> None:
    responses = [response(mrc="45000.00") for _ in range(5)]

    summary = summarize_field(responses, "mrc")

    assert summary.distinct_count == 1
    assert summary.modal_value == "45000.00"
    assert summary.modal_rate == 1.0


def test_mixed_values_report_correct_distinct_count_and_modal() -> None:
    responses = [response(mrc="25000.00")] * 3 + [response(mrc="0.00")] * 2

    summary = summarize_field(responses, "mrc")

    assert summary.distinct_count == 2
    assert summary.modal_value == "25000.00"
    assert summary.modal_rate == 3 / 5


def test_field_missing_from_a_response_counts_as_absent() -> None:
    responses = [response(mrc="45000.00"), response(otc="1000.00")]

    summary = summarize_field(responses, "mrc")

    assert summary.distinct_count == 2
    assert ABSENT in [summary.modal_value] or summary.modal_rate == 0.5


def test_null_value_is_distinct_from_absent_field() -> None:
    present_null = {"fields": {"mrc": {"value": None}}}
    absent = {"fields": {}}

    summary = summarize_field([present_null, absent], "mrc")

    assert summary.distinct_count == 2


def test_unparseable_response_counts_as_invalid_not_absent() -> None:
    responses = [response(mrc="45000.00"), None]

    summary = summarize_field(responses, "mrc")

    assert summary.distinct_count == 2
    assert summary.modal_rate == 0.5


def test_invalid_and_absent_are_distinguishable() -> None:
    unparseable = None
    parseable_but_missing_field = {"fields": {}}

    summary = summarize_field([unparseable, parseable_but_missing_field], "mrc")

    assert summary.distinct_count == 2


def test_summarize_all_covers_every_requested_field_in_order() -> None:
    responses = [response(mrc="45000.00", otc="1000.00")]

    summaries = summarize_all(responses, ["mrc", "otc", "iban"])

    assert [s.field for s in summaries] == ["mrc", "otc", "iban"]
    assert summaries[2].distinct_count == 1
    assert summaries[2].modal_value is ABSENT


def test_render_table_has_header_and_one_row_per_field() -> None:
    responses = [response(mrc="45000.00") for _ in range(4)]
    summaries = summarize_all(responses, ["mrc"])

    table = render_table(summaries)
    lines = table.splitlines()

    assert lines[0].split()[:2] == ["field", "distinct"]
    assert any("mrc" in line for line in lines)
    assert any("100%" in line for line in lines)


def test_render_table_displays_absent_and_invalid_and_null_distinctly() -> None:
    summaries = summarize_all([None, {"fields": {}}, {"fields": {"mrc": {"value": None}}}], ["mrc"])

    table = render_table(summaries)

    assert "<invalid>" in table or "<absent>" in table or "null" in table


def test_invalid_response_sentinel_and_absent_sentinel_are_not_equal() -> None:
    assert ABSENT != INVALID_RESPONSE
