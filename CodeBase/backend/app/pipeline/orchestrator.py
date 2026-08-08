from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from jsonschema import Draft202012Validator, ValidationError
from sqlalchemy.orm import Session

from app.db.documents import DocumentRecord
from app.db.models import Document, Extraction
from app.pipeline.gates.arithmetic import check_arithmetic
from app.pipeline.gates.base import GateResult, GateState
from app.pipeline.gates.iban import check_iban
from app.pipeline.llm.client import LLMClient
from app.pipeline.llm.prompt_builder import build_prompt
from app.pipeline.llm.repair import RepairExhaustedError, complete_with_repair
from app.pipeline.ocr.paddle import ENGINE_VERSION, TextRegion
from app.schemas.extraction import extraction_schema, model_output_schema, schema_version

OCR_URDU_VERSION = "qaari-0.1-urdu"

GateRunner = Callable[[Mapping[str, Any]], Sequence[GateResult]]


class OrchestratorError(RuntimeError):
    stage: str = "orchestrator"


class OCRFailedError(OrchestratorError):
    stage = "ocr"


class ExtractionFailedError(OrchestratorError):
    stage = "llm_extraction"


class GateCoverageError(OrchestratorError):
    stage = "gates"


class OCRReader(Protocol):
    def read(self, image_path: str, *, page: int = 1) -> Sequence[TextRegion]: ...


def _single(gate: Callable[[Mapping[str, Any]], GateResult]) -> GateRunner:
    def run(extraction: Mapping[str, Any]) -> Sequence[GateResult]:
        return (gate(extraction),)

    return run


DEFAULT_GATES: tuple[GateRunner, ...] = (
    _single(check_iban),
    check_arithmetic,
)


@lru_cache
def _model_output_validator() -> Draft202012Validator:
    return Draft202012Validator(model_output_schema())


@lru_cache
def _money_field_names() -> frozenset[str]:
    properties = extraction_schema()["properties"]["fields"]["properties"]
    return frozenset(
        name for name, spec in properties.items() if spec.get("$ref") == "#/$defs/money_field"
    )


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    result: dict[str, Any]
    status: str
    gates: tuple[GateResult, ...]


def _run_ocr(document: DocumentRecord, ocr: OCRReader) -> list[TextRegion]:
    if not document.storage_path:
        raise OCRFailedError(f"document {document.document_id} has no storage_path to read")
    found = list(ocr.read(document.storage_path, page=1))
    if not any(region.text.strip() for region in found):
        raise OCRFailedError(f"OCR produced no usable text for document {document.document_id}")
    return found


def _format_validation_error(error: ValidationError) -> str:
    path = ".".join(str(part) for part in error.path) or "<root>"
    if error.validator == "type":
        expected = error.validator_value
        expected_str = " or ".join(expected) if isinstance(expected, list) else str(expected)
        return f"{path} must be of type {expected_str}, got {json.dumps(error.instance)}"
    return f"{path}: {error.message}"


def _validate_model_output(parsed: Mapping[str, Any]) -> None:
    errors = sorted(_model_output_validator().iter_errors(parsed), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(_format_validation_error(e) for e in errors)
        raise ExtractionFailedError(f"LLM output failed schema validation: {detail}")


def _reset_verification(fields: dict[str, Any]) -> None:
    for entry in fields.values():
        entry["verified"] = False
        entry["gate"] = None
        entry["gate_error"] = None


def _apply_gates(fields: dict[str, Any], results: Sequence[GateResult]) -> None:
    verified_by_field: dict[str, bool] = {}
    for result in results:
        passed = result.state is GateState.PASSED
        for name in result.affected_fields:
            entry = fields.get(name)
            if entry is None:
                continue
            entry["gate"] = result.name
            entry["gate_error"] = None if passed else result.detail
            verified_by_field[name] = verified_by_field.get(name, True) and passed
    for name, verified in verified_by_field.items():
        fields[name]["verified"] = verified


def _assert_money_fields_gated(fields: Mapping[str, Any]) -> None:
    ungated = sorted(
        name
        for name in _money_field_names()
        if name in fields
        and fields[name].get("value") is not None
        and fields[name].get("gate") is None
    )
    if ungated:
        raise GateCoverageError(
            "INV-1: money field(s) "
            f"{', '.join(ungated)} reached persistence with no gate verdict attached"
        )


def _needs_review(fields: Mapping[str, Any]) -> bool:
    populated = [entry for entry in fields.values() if entry.get("value") is not None]
    return not all(entry.get("verified") for entry in populated)


def _pipeline_version(llm: LLMClient, prompt: str) -> dict[str, str]:
    digest = hashlib.sha256(prompt.encode()).hexdigest()[:12]
    return {
        "profile": llm.profile.value,
        "ocr_latin": ENGINE_VERSION,
        "ocr_urdu": OCR_URDU_VERSION,
        "llm": llm.model,
        "prompt_hash": f"sha256:{digest}",
        "schema_version": schema_version(),
    }


def extract(
    document: DocumentRecord,
    *,
    ocr: OCRReader,
    llm: LLMClient,
    gates: Sequence[GateRunner] = DEFAULT_GATES,
    build_prompt_fn: Callable[[Sequence[TextRegion]], str] = build_prompt,
    max_repair_retries: int = 1,
) -> ExtractionOutcome:
    text_regions = _run_ocr(document, ocr)
    prompt = build_prompt_fn(text_regions)
    try:
        parsed = complete_with_repair(
            lambda p: llm.complete(p, document=document),
            prompt,
            validate=_validate_model_output,
            max_retries=max_repair_retries,
        )
    except RepairExhaustedError as exc:
        raise ExtractionFailedError(str(exc)) from exc

    fields: dict[str, Any] = dict(parsed.get("fields") or {})
    _reset_verification(fields)

    extraction_view = {"fields": fields, "line_items": parsed.get("line_items", [])}
    gate_results: list[GateResult] = []
    for gate in gates:
        gate_results.extend(gate(extraction_view))

    _apply_gates(fields, gate_results)
    _assert_money_fields_gated(fields)

    status = "needs_review" if _needs_review(fields) else "complete"

    result: dict[str, Any] = {
        "document_id": document.document_id,
        "pipeline_version": _pipeline_version(llm, prompt),
        "status": status,
        "document_type": parsed.get("document_type", {"value": "unknown", "confidence": 0.0}),
        "fields": fields,
        "gates": [
            {
                "name": r.name,
                "result": r.state.value,
                "detail": r.detail,
                "affected_fields": list(r.affected_fields),
            }
            for r in gate_results
        ],
        "review": {"required": status != "complete"},
    }
    if "language" in parsed:
        result["language"] = parsed["language"]
    if "line_items" in parsed:
        result["line_items"] = parsed["line_items"]

    return ExtractionOutcome(result=result, status=status, gates=tuple(gate_results))


def run_and_persist(
    session: Session,
    document: Document,
    *,
    ocr: OCRReader,
    llm: LLMClient,
    gates: Sequence[GateRunner] = DEFAULT_GATES,
    build_prompt_fn: Callable[[Sequence[TextRegion]], str] = build_prompt,
    max_repair_retries: int = 1,
) -> Extraction:
    record = DocumentRecord(
        document_id=str(document.id),
        filename=document.filename,
        data_classification=document.data_classification,  # type: ignore[arg-type]
        uploaded_at=document.uploaded_at.isoformat() if document.uploaded_at else None,
        storage_path=document.storage_path,
    )
    outcome = extract(
        record,
        ocr=ocr,
        llm=llm,
        gates=gates,
        build_prompt_fn=build_prompt_fn,
        max_repair_retries=max_repair_retries,
    )

    extraction_id = uuid.uuid4()
    outcome.result["extraction_id"] = str(extraction_id)

    row = Extraction(
        id=extraction_id,
        document_id=document.id,
        pipeline_version=outcome.result["pipeline_version"],
        result=outcome.result,
        status=outcome.status,
    )
    session.add(row)
    document.status = outcome.status
    session.commit()
    return row
