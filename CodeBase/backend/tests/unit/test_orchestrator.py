from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from app.db.documents import DocumentRecord
from app.pipeline.gates.base import GateResult, GateState
from app.pipeline.llm.client import (
    DeploymentProfile,
    Endpoint,
    HostedEndpointRefusedError,
    LLMClient,
)
from app.pipeline.llm.prompt_builder import build_prompt
from app.pipeline.llm.transport import TruncatedResponseError
from app.pipeline.ocr.paddle import TextRegion
from app.pipeline.orchestrator import (
    DEFAULT_GATES,
    DocumentTooLargeError,
    ExtractionFailedError,
    GateCoverageError,
    OCRFailedError,
    extract,
)

IBAN_VALID = "PK36SCBL0000001123456702"
IBAN_BAD_CHECKSUM = "PK70BANK0000001234567890"


class FakeOCR:
    def __init__(
        self,
        regions: Sequence[TextRegion] | Mapping[int, Sequence[TextRegion]],
        *,
        page_count: int | None = None,
    ) -> None:
        if isinstance(regions, Mapping):
            self._pages: dict[int, list[TextRegion]] = {
                page: list(page_regions) for page, page_regions in regions.items()
            }
        else:
            self._pages = {1: list(regions)}
        self._page_count = page_count if page_count is not None else max(self._pages, default=1)
        self.read_calls: list[int] = []

    def read(self, image_path: str, *, page: int = 1) -> Sequence[TextRegion]:
        self.read_calls.append(page)
        return self._pages.get(page, [])

    def page_count(self, image_path: str) -> int:
        return self._page_count


class Spy:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


class SequenceSpy:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        index = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[index]


class TruncatingSpy:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        raise TruncatedResponseError(self.content)


def regions(text: str = "PO Number: PO-2291\nTotal: 11700.00") -> list[TextRegion]:
    return [TextRegion(text=text, confidence=0.9, bbox=(0.1, 0.1, 0.5, 0.2), page=1)]


def empty_regions() -> list[TextRegion]:
    return [TextRegion(text="   ", confidence=0.1, bbox=(0.0, 0.0, 0.0, 0.0), page=1)]


def document(
    classification: str = "synthetic", storage_path: str = "var/uploads/aa/doc.pdf"
) -> DocumentRecord:
    return DocumentRecord(
        document_id="doc-1",
        filename="doc.pdf",
        data_classification=classification,  # type: ignore[arg-type]
        storage_path=storage_path,
    )


def hosted_llm(response: str) -> tuple[LLMClient, Spy]:
    spy = Spy(response)
    client = LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model="fake-hosted-model",
        transport=spy,
    )
    return client, spy


def hosted_llm_sequence(responses: list[str]) -> tuple[LLMClient, SequenceSpy]:
    spy = SequenceSpy(responses)
    client = LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model="fake-hosted-model",
        transport=spy,
    )
    return client, spy


def truncating_hosted_llm(content: str) -> tuple[LLMClient, TruncatingSpy]:
    spy = TruncatingSpy(content)
    client = LLMClient(
        profile=DeploymentProfile.PROTOTYPE,
        endpoint=Endpoint.HOSTED,
        model="fake-hosted-model",
        transport=spy,
    )
    return client, spy


def llm_field(
    value: Any,
    confidence: float = 0.9,
    verified: bool = False,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence,
        "verified": verified,
        "source": source or {"origin": "llm_inferred"},
    }


def llm_body(
    fields: dict[str, Any],
    *,
    document_type: str = "invoice",
    line_items: list[dict[str, Any]] | None = None,
) -> str:
    body: dict[str, Any] = {
        "document_type": {"value": document_type, "confidence": 0.95},
        "fields": fields,
    }
    if line_items is not None:
        body["line_items"] = line_items
    return json.dumps(body)


def _line_item(quantity: str, unit_price: str, line_total: str) -> dict[str, Any]:
    return {
        "description": llm_field("Managed router"),
        "quantity": llm_field(quantity),
        "unit_price": llm_field(unit_price),
        "line_total": llm_field(line_total),
    }


def test_happy_path_all_gates_pass_routes_complete() -> None:
    fields = {
        "iban": llm_field(IBAN_VALID, confidence=0.5, verified=True),
        "subtotal": llm_field("10000.00"),
        "tax": llm_field("1700.00"),
        "total": llm_field("11700.00"),
    }
    line_items = [_line_item("1", "10000.00", "10000.00")]
    llm, spy = hosted_llm(llm_body(fields, line_items=line_items))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.status == "complete"
    assert outcome.result["fields"]["iban"]["verified"] is True
    assert outcome.result["fields"]["iban"]["gate"] == "iban_checksum"
    assert outcome.result["fields"]["subtotal"]["verified"] is True
    assert outcome.result["fields"]["total"]["verified"] is True
    assert outcome.result["review"]["required"] is False
    gate_names = {g["name"] for g in outcome.result["gates"]}
    assert {"iban_checksum", "line_item_sum", "arithmetic_reconciliation"} <= gate_names
    assert len(spy.calls) == 1


def test_ocr_empty_text_fails_fast_before_llm_is_called() -> None:
    llm, spy = hosted_llm(llm_body({}))

    with pytest.raises(OCRFailedError):
        extract(document(), ocr=FakeOCR(empty_regions()), llm=llm)

    assert spy.calls == [], "empty OCR text must never reach the LLM"


def test_llm_invalid_json_raises_extraction_failed() -> None:
    llm, _spy = hosted_llm("this is not json")

    with pytest.raises(ExtractionFailedError):
        extract(document(), ocr=FakeOCR(regions()), llm=llm)


def test_llm_output_missing_source_fails_the_whole_stage_no_partial_accept() -> None:
    bad = json.dumps(
        {
            "document_type": {"value": "invoice", "confidence": 0.9},
            "fields": {"po_number": {"value": "PO-1", "confidence": 0.9, "verified": False}},
        }
    )
    llm, _spy = hosted_llm(bad)

    with pytest.raises(ExtractionFailedError):
        extract(document(), ocr=FakeOCR(regions()), llm=llm)


def test_failed_gate_overrides_high_model_confidence() -> None:
    fields = {"iban": llm_field(IBAN_BAD_CHECKSUM, confidence=0.99, verified=True)}
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    field = outcome.result["fields"]["iban"]
    assert field["verified"] is False
    assert field["gate_error"] is not None
    assert outcome.status == "needs_review"


def test_model_cannot_self_verify_a_field_no_gate_touches() -> None:
    fields = {"customer_name": llm_field("Acme Textiles", confidence=0.99, verified=True)}
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    field = outcome.result["fields"]["customer_name"]
    assert field["verified"] is False
    assert field["gate"] is None


def test_inv6_guard_is_on_the_path_restricted_document_refused_before_transport() -> None:
    llm, spy = hosted_llm(llm_body({}))

    with pytest.raises(HostedEndpointRefusedError):
        extract(document(classification="restricted"), ocr=FakeOCR(regions()), llm=llm)

    assert spy.calls == [], "the guard must refuse before the transport is ever reached"


def test_money_field_with_no_gate_coverage_is_refused() -> None:
    fields = {"subtotal": llm_field("10000.00"), "tax": llm_field("1700.00")}
    llm, _spy = hosted_llm(llm_body(fields))

    with pytest.raises(GateCoverageError, match="subtotal"):
        extract(document(), ocr=FakeOCR(regions()), llm=llm, gates=())


def test_pipeline_version_is_stamped_with_profile_model_and_prompt_hash() -> None:
    llm, _spy = hosted_llm(llm_body({}))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    version = outcome.result["pipeline_version"]
    assert version["profile"] == "prototype"
    assert version["llm"] == "fake-hosted-model"
    assert version["ocr_latin"] == "paddleocr-pp-ocrv5"
    assert version["schema_version"] == "0.3.1"
    assert version["prompt_hash"] == f"sha256:{_expected_hash(regions())}"


def _expected_hash(text_regions: list[TextRegion]) -> str:
    import hashlib

    prompt = build_prompt(text_regions)
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


def test_gate_registry_is_pluggable_without_orchestrator_changes() -> None:
    def fake_gate(extraction: dict[str, Any]) -> tuple[GateResult, ...]:
        return (
            GateResult(
                name="fake_check",
                state=GateState.PASSED,
                detail="ok",
                affected_fields=("customer_name",),
            ),
        )

    fields = {"customer_name": llm_field("Acme Textiles")}
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(
        document(), ocr=FakeOCR(regions()), llm=llm, gates=(*DEFAULT_GATES, fake_gate)
    )

    gate_names = {g["name"] for g in outcome.result["gates"]}
    assert "fake_check" in gate_names
    assert outcome.result["fields"]["customer_name"]["verified"] is True


def test_needs_review_when_any_present_field_has_no_verifying_gate() -> None:
    fields = {
        "iban": llm_field(IBAN_VALID),
        "po_number": llm_field("PO-2291"),
    }
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.status == "needs_review"


def test_zero_populated_fields_routes_to_needs_review_not_complete() -> None:
    llm, _spy = hosted_llm(llm_body({}))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.status == "needs_review"
    assert outcome.result["review"]["required"] is True


def test_all_populated_fields_verified_routes_to_complete() -> None:
    fields = {"iban": llm_field(IBAN_VALID)}
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.result["fields"]["iban"]["verified"] is True
    assert outcome.status == "complete"
    assert outcome.result["review"]["required"] is False


def test_some_populated_fields_unverified_routes_to_needs_review() -> None:
    fields = {
        "iban": llm_field(IBAN_VALID),
        "po_number": llm_field("PO-2291"),
    }
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.result["fields"]["iban"]["verified"] is True
    assert outcome.result["fields"]["po_number"]["verified"] is False
    assert outcome.status == "needs_review"


def test_null_valued_fields_do_not_block_completion() -> None:
    fields = {
        "iban": llm_field(IBAN_VALID),
        "subtotal": llm_field("10000.00"),
        "tax": llm_field("1700.00"),
        "total": llm_field("11700.00"),
        "notes": llm_field(None, confidence=0.0),
    }
    line_items = [_line_item("1", "10000.00", "10000.00")]
    llm, _spy = hosted_llm(llm_body(fields, line_items=line_items))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.status == "complete"


def test_malformed_llm_output_is_repaired_once_then_succeeds() -> None:
    fields = {"iban": llm_field(IBAN_VALID)}
    llm, spy = hosted_llm_sequence(["not valid json at all", llm_body(fields)])

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.result["fields"]["iban"]["verified"] is True
    assert len(spy.calls) == 2
    assert "not valid json at all" in spy.calls[1]


def test_llm_invalid_json_twice_exhausts_repair_and_raises() -> None:
    llm, spy = hosted_llm_sequence(["still not json", "still not json"])

    with pytest.raises(ExtractionFailedError):
        extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert len(spy.calls) == 2


def test_truncated_response_recovers_complete_fields_and_routes_needs_review() -> None:
    po_field = llm_field("PO-2291", source={"origin": "llm_inferred", "raw_text": "PO-2291"})
    iban_field = llm_field(IBAN_VALID, source={"origin": "llm_inferred", "raw_text": IBAN_VALID})
    truncated_body = (
        '{"document_type": {"value": "invoice", "confidence": 0.95}, "fields": {'
        f'"po_number": {json.dumps(po_field)}, '
        f'"iban": {json.dumps(iban_field)}, '
        '"notes": {"value": "terms and conditions that go on for a while and then just sto'
    )
    llm, spy = truncating_hosted_llm(truncated_body)

    outcome = extract(document(), ocr=FakeOCR(regions(IBAN_VALID)), llm=llm)

    assert outcome.truncated is True
    assert outcome.status == "needs_review"
    assert outcome.result["review"] == {"required": True, "reason": "llm_output_truncated"}
    assert set(outcome.result["fields"]) == {"po_number", "iban"}
    assert outcome.result["fields"]["iban"]["verified"] is True, (
        "gates must still run normally over whatever survived salvage"
    )


def test_truncated_response_is_not_retried_via_the_repair_prompt_loop() -> None:
    truncated_body = (
        '{"document_type": {"value": "invoice", "confidence": 0.95}, "fields": {'
        f'"po_number": {json.dumps(llm_field("PO-2291"))}, "notes": {{"value": "cut off mid-strin'
    )
    llm, spy = truncating_hosted_llm(truncated_body)

    extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert len(spy.calls) == 1, "truncation must bypass complete_with_repair's retry loop entirely"


def test_truncated_response_with_nothing_recoverable_raises_extraction_failed() -> None:
    llm, spy = truncating_hosted_llm('{"document_type": {"value": "in')

    with pytest.raises(ExtractionFailedError, match="truncated"):
        extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert len(spy.calls) == 1


def test_truncated_response_drops_an_incomplete_field_entry_but_keeps_the_complete_ones() -> None:
    truncated_body = (
        '{"document_type": {"value": "invoice", "confidence": 0.95}, "fields": {'
        f'"po_number": {json.dumps(llm_field("PO-2291"))}, '
        '"total": {"value": "45000.0'
    )
    llm, spy = truncating_hosted_llm(truncated_body)

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.truncated is True
    assert "po_number" in outcome.result["fields"]
    assert "total" not in outcome.result["fields"], (
        "an entry missing confidence/verified/source after salvage must be dropped, not guessed at"
    )


def _body_with_null_raw_text() -> str:
    return json.dumps(
        {
            "document_type": {"value": "invoice", "confidence": 0.95},
            "fields": {
                "mrc": {
                    "value": None,
                    "confidence": 0.0,
                    "verified": False,
                    "source": {"origin": "llm_inferred", "raw_text": None},
                }
            },
        }
    )


def test_schema_valid_but_rejected_output_is_repaired_once_then_succeeds() -> None:
    fields = {"iban": llm_field(IBAN_VALID)}
    llm, spy = hosted_llm_sequence([_body_with_null_raw_text(), llm_body(fields)])

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert outcome.result["fields"]["iban"]["verified"] is True
    assert len(spy.calls) == 2
    assert "fields.mrc.source.raw_text" in spy.calls[1]
    assert "must be of type string, got null" in spy.calls[1]


def test_schema_valid_but_rejected_output_twice_exhausts_repair_and_raises() -> None:
    llm, spy = hosted_llm_sequence([_body_with_null_raw_text(), _body_with_null_raw_text()])

    with pytest.raises(ExtractionFailedError, match="must be of type string, got null"):
        extract(document(), ocr=FakeOCR(regions()), llm=llm)

    assert len(spy.calls) == 2


def test_field_with_matching_raw_text_gets_bbox_and_page_attached() -> None:
    fields = {
        "po_number": llm_field(
            "PO-2291", source={"origin": "llm_inferred", "raw_text": "PO Number: PO-2291"}
        )
    }
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    source = outcome.result["fields"]["po_number"]["source"]
    assert source["page"] == 1
    assert source["bbox"] == [0.1, 0.1, 0.5, 0.2]


def test_field_with_unmatched_raw_text_does_not_raise_and_routes_needs_review() -> None:
    fields = {
        "iban": llm_field(
            IBAN_VALID,
            source={"origin": "llm_inferred", "raw_text": "text not present in OCR output"},
        )
    }
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    source = outcome.result["fields"]["iban"]["source"]
    assert "bbox" not in source
    assert "page" not in source
    assert outcome.status == "needs_review"


def test_field_without_raw_text_has_no_bbox_and_can_still_complete() -> None:
    fields = {"iban": llm_field(IBAN_VALID)}
    llm, _spy = hosted_llm(llm_body(fields))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    source = outcome.result["fields"]["iban"]["source"]
    assert "bbox" not in source
    assert outcome.status == "complete"


def test_multipage_document_feeds_regions_from_every_page_into_the_extraction() -> None:
    fields = {
        "iban": llm_field(
            IBAN_VALID, source={"origin": "llm_inferred", "raw_text": "IBAN: " + IBAN_VALID}
        ),
        "po_number": llm_field(
            "PO-2291", source={"origin": "llm_inferred", "raw_text": "PO Number: PO-2291"}
        ),
    }
    llm, _spy = hosted_llm(llm_body(fields))
    ocr = FakeOCR(
        {
            1: [TextRegion(text="Cover Page", confidence=0.9, bbox=(0.1, 0.1, 0.5, 0.2), page=1)],
            2: [
                TextRegion(
                    text="PO Number: PO-2291",
                    confidence=0.9,
                    bbox=(0.1, 0.1, 0.5, 0.2),
                    page=2,
                )
            ],
            3: [
                TextRegion(
                    text="IBAN: " + IBAN_VALID,
                    confidence=0.9,
                    bbox=(0.2, 0.2, 0.6, 0.3),
                    page=3,
                )
            ],
        }
    )

    outcome = extract(document(), ocr=ocr, llm=llm)

    assert ocr.read_calls == [1, 2, 3]
    assert outcome.result["fields"]["po_number"]["source"]["page"] == 2
    assert outcome.result["fields"]["iban"]["source"]["page"] == 3


def test_field_claimed_only_on_page_three_resolves_source_page_three_end_to_end() -> None:
    fields = {
        "customer_name": llm_field(
            "Acme Textiles",
            source={"origin": "llm_inferred", "raw_text": "Customer: Acme Textiles"},
        )
    }
    llm, _spy = hosted_llm(llm_body(fields))
    ocr = FakeOCR(
        {
            1: [
                TextRegion(
                    text="Cover page only", confidence=0.9, bbox=(0.0, 0.0, 1.0, 1.0), page=1
                )
            ],
            2: [
                TextRegion(
                    text="Unrelated page two text",
                    confidence=0.9,
                    bbox=(0.0, 0.0, 1.0, 1.0),
                    page=2,
                )
            ],
            3: [
                TextRegion(
                    text="Customer: Acme Textiles",
                    confidence=0.9,
                    bbox=(0.1, 0.1, 0.6, 0.2),
                    page=3,
                )
            ],
        }
    )

    outcome = extract(document(), ocr=ocr, llm=llm)

    assert outcome.result["fields"]["customer_name"]["source"]["page"] == 3


def test_page_count_exceeding_max_pdf_pages_raises_before_any_ocr_read() -> None:
    llm, spy = hosted_llm(llm_body({}))
    ocr = FakeOCR(regions(), page_count=51)

    with pytest.raises(DocumentTooLargeError):
        extract(document(), ocr=ocr, llm=llm, max_pdf_pages=50)

    assert ocr.read_calls == [], "read() must never be called once the page cap is exceeded"
    assert spy.calls == []


def test_page_count_exactly_at_the_cap_is_allowed() -> None:
    llm, _spy = hosted_llm(llm_body({}))
    ocr = FakeOCR(regions(), page_count=1)

    outcome = extract(document(), ocr=ocr, llm=llm, max_pdf_pages=1)

    assert ocr.read_calls == [1]
    assert outcome.status == "needs_review"


def test_ocr_text_exceeding_max_input_tokens_raises_before_the_llm_is_called() -> None:
    llm, spy = hosted_llm(llm_body({}))
    huge_text = "x" * 1000
    ocr = FakeOCR([TextRegion(text=huge_text, confidence=0.9, bbox=(0.0, 0.0, 1.0, 1.0), page=1)])

    with pytest.raises(DocumentTooLargeError):
        extract(document(), ocr=ocr, llm=llm, max_input_tokens=10)

    assert spy.calls == [], "the LLM transport must never be reached once the input budget is blown"


def test_line_item_field_provenance_is_attached() -> None:
    fields = {
        "iban": llm_field(IBAN_VALID),
        "subtotal": llm_field("10000.00"),
        "tax": llm_field("1700.00"),
        "total": llm_field("11700.00"),
    }
    line_items = [
        {
            "description": llm_field(
                "Managed router",
                source={"origin": "llm_inferred", "raw_text": "Total: 11700.00"},
            ),
            "quantity": llm_field("1"),
            "unit_price": llm_field("10000.00"),
            "line_total": llm_field("10000.00"),
        }
    ]
    llm, _spy = hosted_llm(llm_body(fields, line_items=line_items))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    source = outcome.result["line_items"][0]["description"]["source"]
    assert source["bbox"] == [0.1, 0.1, 0.5, 0.2]
