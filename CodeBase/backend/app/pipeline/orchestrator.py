from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import json_repair
from jsonschema import Draft202012Validator, ValidationError
from sqlalchemy.orm import Session

from app.core.errors import envelope
from app.db.documents import DocumentRecord
from app.db.models import Document, Extraction
from app.pipeline.gates.arithmetic import check_arithmetic
from app.pipeline.gates.base import GateResult, GateState
from app.pipeline.gates.iban import check_iban
from app.pipeline.llm.client import LLMClient
from app.pipeline.llm.prompt_builder import build_prompt
from app.pipeline.llm.repair import RepairExhaustedError, complete_with_repair
from app.pipeline.llm.transport import TruncatedResponseError
from app.pipeline.ocr.paddle import ENGINE_VERSION, TextRegion
from app.pipeline.provenance import ProvenanceReport, attach_provenance
from app.schemas.extraction import extraction_schema, model_output_schema, schema_version

logger = logging.getLogger("app")

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


class DocumentTooLargeError(OrchestratorError):
    stage = "input_budget"


class OCRReader(Protocol):
    def read(self, image_path: str, *, page: int = 1) -> Sequence[TextRegion]: ...
    def page_count(self, image_path: str) -> int: ...


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


LINE_ITEM_MONEY_FIELDS = frozenset({"unit_price", "line_total"})


@lru_cache
def _field_entry_validator() -> Draft202012Validator:
    schema = extraction_schema()
    return Draft202012Validator({"$ref": "#/$defs/field", "$defs": schema["$defs"]})


@lru_cache
def _money_field_entry_validator() -> Draft202012Validator:
    schema = extraction_schema()
    return Draft202012Validator({"$ref": "#/$defs/money_field", "$defs": schema["$defs"]})


def _entry_validator(name: str, *, is_line_item: bool) -> Draft202012Validator:
    money = name in LINE_ITEM_MONEY_FIELDS if is_line_item else name in _money_field_names()
    return _money_field_entry_validator() if money else _field_entry_validator()


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    result: dict[str, Any]
    status: str
    gates: tuple[GateResult, ...]
    truncated: bool = False


def _run_ocr(document: DocumentRecord, ocr: OCRReader, max_pdf_pages: int) -> list[TextRegion]:
    if not document.storage_path:
        raise OCRFailedError(f"document {document.document_id} has no storage_path to read")
    count = ocr.page_count(document.storage_path)
    if count > max_pdf_pages:
        raise DocumentTooLargeError(
            f"document {document.document_id} has {count} pages, exceeding the max_pdf_pages "
            f"cap of {max_pdf_pages}"
        )
    found: list[TextRegion] = []
    for page in range(1, count + 1):
        found.extend(ocr.read(document.storage_path, page=page))
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


def _salvage_truncated_output(content: str) -> dict[str, Any] | None:
    """Best-effort recovery from a response cut short by max_tokens (finish_reason == "length").

    Not a repair-prompt retry — asking the model to fix output that is not wrong, only unfinished,
    just produces another long response with the same chance of truncating again
    ([[ADR-015-truncated-llm-output-is-salvaged-not-repaired]]). Instead: close out whatever JSON
    the model had actually finished generating, keep only the field/line-item entries that are
    individually well-formed, and drop anything that was mid-flight when generation stopped rather
    than guess at it. Returns None — the genuine-failure case — if nothing usable survives; the
    caller fails loudly in that case, exactly as it would for any other unparseable response.
    """
    try:
        repaired = json_repair.repair_json(content, return_objects=True)
    except Exception:
        return None
    if not isinstance(repaired, dict):
        return None

    fields = repaired.get("fields")
    cleaned_fields: dict[str, Any] = {}
    if isinstance(fields, dict):
        for name, entry in fields.items():
            validator = _entry_validator(name, is_line_item=False)
            if isinstance(entry, dict) and validator.is_valid(entry):
                cleaned_fields[name] = entry
    repaired["fields"] = cleaned_fields

    line_items = repaired.get("line_items")
    cleaned_line_items: list[dict[str, Any]] = []
    if isinstance(line_items, list):
        for item in line_items:
            if not isinstance(item, dict):
                continue
            cleaned_item = {
                name: entry
                for name, entry in item.items()
                if isinstance(entry, dict)
                and _entry_validator(name, is_line_item=True).is_valid(entry)
            }
            if cleaned_item:
                cleaned_line_items.append(cleaned_item)
    repaired["line_items"] = cleaned_line_items

    if not cleaned_fields and not cleaned_line_items:
        return None

    try:
        _validate_model_output(repaired)
    except ExtractionFailedError:
        return None
    return repaired


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


def _log_provenance(document_id: str, report: ProvenanceReport) -> None:
    if report.unmatched_claims:
        logger.warning(
            "extraction %s: provenance unmatched for field(s) %s",
            document_id,
            ", ".join(report.unmatched_claims),
        )
    logger.info(
        "extraction %s: provenance %d/%d claimed fields resolved (%d populated)",
        document_id,
        report.resolved_fields,
        report.claimed_fields,
        report.populated_fields,
    )


def _needs_review(fields: Mapping[str, Any], unmatched_claims: Sequence[str] = ()) -> bool:
    populated = [entry for entry in fields.values() if entry.get("value") is not None]
    if not populated:
        return True
    if unmatched_claims:
        return True
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
    max_pdf_pages: int = 50,
    max_input_tokens: int = 20000,
) -> ExtractionOutcome:
    text_regions = _run_ocr(document, ocr, max_pdf_pages)

    joined_text = "\n".join(region.text for region in text_regions if region.text.strip())
    estimated_tokens = len(joined_text) // 4
    if estimated_tokens > max_input_tokens:
        raise DocumentTooLargeError(
            f"document {document.document_id} OCR text is ~{estimated_tokens} tokens, exceeding "
            f"the max_input_tokens cap of {max_input_tokens}"
        )

    prompt = build_prompt_fn(text_regions)
    truncated = False
    try:
        parsed = complete_with_repair(
            lambda p: llm.complete(p, document=document),
            prompt,
            validate=_validate_model_output,
            max_retries=max_repair_retries,
        )
    except TruncatedResponseError as exc:
        salvaged = _salvage_truncated_output(exc.content)
        if salvaged is None:
            raise ExtractionFailedError(
                "LLM output was truncated by the token limit and no usable field or line item "
                "survived recovery"
            ) from exc
        parsed = salvaged
        truncated = True
    except RepairExhaustedError as exc:
        raise ExtractionFailedError(str(exc)) from exc

    fields: dict[str, Any] = dict(parsed.get("fields") or {})
    _reset_verification(fields)
    line_items: list[dict[str, Any]] = list(parsed.get("line_items") or [])

    provenance = attach_provenance(fields, line_items, text_regions)
    _log_provenance(document.document_id, provenance)

    extraction_view = {"fields": fields, "line_items": line_items}
    gate_results: list[GateResult] = []
    for gate in gates:
        gate_results.extend(gate(extraction_view))

    _apply_gates(fields, gate_results)
    _assert_money_fields_gated(fields)

    # A truncated response is forced to needs_review regardless of what the ordinary heuristic
    # would say — a salvage is itself a fallible check (same class as provenance-merge, ADR-012)
    # and must never be authoritative enough to promote a document to complete on its own.
    status = (
        "needs_review"
        if truncated or _needs_review(fields, provenance.unmatched_claims)
        else "complete"
    )

    review: dict[str, Any] = {"required": status != "complete"}
    if truncated:
        review["reason"] = "llm_output_truncated"

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
        "review": review,
    }
    if "language" in parsed:
        result["language"] = parsed["language"]
    if "line_items" in parsed:
        result["line_items"] = line_items

    return ExtractionOutcome(
        result=result, status=status, gates=tuple(gate_results), truncated=truncated
    )


def run_and_persist(
    session: Session,
    document: Document,
    *,
    ocr: OCRReader,
    llm: LLMClient,
    gates: Sequence[GateRunner] = DEFAULT_GATES,
    build_prompt_fn: Callable[[Sequence[TextRegion]], str] = build_prompt,
    max_repair_retries: int = 1,
    max_pdf_pages: int = 50,
    max_input_tokens: int = 20000,
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
        max_pdf_pages=max_pdf_pages,
        max_input_tokens=max_input_tokens,
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
    document.document_type = outcome.result["document_type"]["value"]
    if outcome.truncated:
        document.error = envelope(
            "LLM_OUTPUT_TRUNCATED",
            "The model's response was cut off by the output token limit before it finished. "
            "This extraction is a partial recovery — some fields may be missing. Review before "
            "trusting it as complete.",
            str(uuid.uuid4()),
        )["error"]
    else:
        document.error = None
    session.commit()
    return row
