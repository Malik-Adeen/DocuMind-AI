from __future__ import annotations

import json
from collections.abc import Sequence
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
from app.pipeline.ocr.paddle import TextRegion
from app.pipeline.orchestrator import (
    DEFAULT_GATES,
    ExtractionFailedError,
    GateCoverageError,
    OCRFailedError,
    extract,
)

IBAN_VALID = "PK36SCBL0000001123456702"
IBAN_BAD_CHECKSUM = "PK70BANK0000001234567890"


class FakeOCR:
    def __init__(self, regions: Sequence[TextRegion]) -> None:
        self._regions = list(regions)

    def read(self, image_path: str, *, page: int = 1) -> Sequence[TextRegion]:
        return self._regions


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
        extract(document(), ocr=FakeOCR(regions()), llm=llm)


def test_pipeline_version_is_stamped_with_profile_model_and_prompt_hash() -> None:
    llm, _spy = hosted_llm(llm_body({}))

    outcome = extract(document(), ocr=FakeOCR(regions()), llm=llm)

    version = outcome.result["pipeline_version"]
    assert version["profile"] == "prototype"
    assert version["llm"] == "fake-hosted-model"
    assert version["ocr_latin"] == "paddleocr-pp-ocrv5"
    assert version["schema_version"] == "0.3.0"
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
