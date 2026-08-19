from __future__ import annotations

from typing import Any

from app.pipeline.ocr.paddle import TextRegion
from app.pipeline.provenance import attach_provenance


def region(
    text: str, bbox: tuple[float, float, float, float] = (0.1, 0.1, 0.5, 0.2), page: int = 1
) -> TextRegion:
    return TextRegion(text=text, confidence=0.9, bbox=bbox, page=page)


def field(value: Any, raw_text: str | None = None, origin: str = "llm_inferred") -> dict[str, Any]:
    source: dict[str, Any] = {"origin": origin}
    if raw_text is not None:
        source["raw_text"] = raw_text
    return {"value": value, "confidence": 0.9, "verified": False, "source": source}


def test_exact_single_region_match_attaches_bbox_and_page() -> None:
    fields = {"po_number": field("PO-2291", raw_text="PO Number: PO-2291")}
    regions = [region("PO Number: PO-2291", bbox=(0.1, 0.1, 0.4, 0.15))]

    report = attach_provenance(fields, [], regions)

    source = fields["po_number"]["source"]
    assert source["page"] == 1
    assert source["bbox"] == [0.1, 0.1, 0.4, 0.15]
    assert "unmatched" not in source
    assert report.claimed_fields == 1
    assert report.resolved_fields == 1
    assert report.unmatched_claims == ()


def test_match_spanning_two_adjacent_regions_unions_bbox() -> None:
    fields = {"customer_name": field("Acme Textiles Pvt Ltd", raw_text="Acme Textiles\nPvt Ltd")}
    regions = [
        region("Acme Textiles", bbox=(0.1, 0.1, 0.3, 0.15)),
        region("Pvt Ltd", bbox=(0.1, 0.16, 0.25, 0.2)),
    ]

    report = attach_provenance(fields, [], regions)

    source = fields["customer_name"]["source"]
    assert source["page"] == 1
    assert source["bbox"] == [0.1, 0.1, 0.3, 0.2]
    assert report.resolved_fields == 1


def test_no_raw_text_is_left_untouched_and_not_counted() -> None:
    fields = {"notes": field(None)}
    regions = [region("some unrelated text")]

    report = attach_provenance(fields, [], regions)

    assert fields["notes"]["source"] == {"origin": "llm_inferred"}
    assert report.claimed_fields == 0
    assert report.unmatched_claims == ()


def test_unmatched_raw_text_is_recorded_not_fabricated() -> None:
    fields = {"iban": field("PK36SCBL0000001123456702", raw_text="IBAN quoted but not present")}
    regions = [region("totally different OCR text")]

    report = attach_provenance(fields, [], regions)

    source = fields["iban"]["source"]
    assert "bbox" not in source
    assert "page" not in source
    assert source["unmatched"] is True
    assert report.unmatched_claims == ("iban",)
    assert report.resolved_fields == 0


def test_unmatched_flag_is_orchestrator_owned_not_model_supplied() -> None:
    claimed_and_matched = field("PO-2291", raw_text="PO Number: PO-2291")
    claimed_and_matched["source"]["unmatched"] = True
    fields = {"po_number": claimed_and_matched}
    regions = [region("PO Number: PO-2291", bbox=(0.1, 0.1, 0.4, 0.15))]

    attach_provenance(fields, [], regions)

    assert "unmatched" not in fields["po_number"]["source"]


def test_non_llm_origin_is_skipped() -> None:
    fields = {"mrc": field("500.00", raw_text="irrelevant", origin="human")}
    regions = [region("irrelevant")]

    report = attach_provenance(fields, [], regions)

    assert "bbox" not in fields["mrc"]["source"]
    assert report.claimed_fields == 0


def test_claim_matched_only_on_page_two_of_a_three_page_document_resolves_that_page() -> None:
    fields = {"po_number": field("PO-2291", raw_text="PO Number: PO-2291")}
    regions = [
        region("Cover page, no useful fields here", bbox=(0.0, 0.0, 1.0, 1.0), page=1),
        region("PO Number: PO-2291", bbox=(0.1, 0.2, 0.5, 0.25), page=2),
        region("Signature page text", bbox=(0.0, 0.0, 1.0, 1.0), page=3),
    ]

    report = attach_provenance(fields, [], regions)

    source = fields["po_number"]["source"]
    assert source["page"] == 2
    assert source["bbox"] == [0.1, 0.2, 0.5, 0.25]
    assert report.resolved_fields == 1


def test_line_item_field_gets_provenance_attached() -> None:
    line_items = [
        {
            "description": field("Managed router", raw_text="Managed router"),
            "quantity": field("1"),
            "unit_price": field("10000.00"),
            "line_total": field("10000.00"),
        }
    ]
    regions = [region("Managed router", bbox=(0.1, 0.3, 0.4, 0.35))]

    report = attach_provenance({}, line_items, regions)

    source = line_items[0]["description"]["source"]
    assert source["bbox"] == [0.1, 0.3, 0.4, 0.35]
    assert report.resolved_fields == 1
