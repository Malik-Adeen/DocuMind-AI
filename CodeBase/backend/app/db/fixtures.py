from __future__ import annotations

from typing import Any

PIPELINE_VERSION: dict[str, Any] = {
    "profile": "prototype",
    "ocr_latin": "paddleocr-pp-ocrv5",
    "ocr_urdu": "qaari-0.1-urdu",
    "llm": "qwen2.5-7b-instruct",
    "prompt_hash": "sha256:2f1a9c",
    "schema_version": "0.3.1",
}

DOC_FAILED_GATE = "11111111-1111-1111-1111-111111111111"
DOC_FORMAT_ONLY = "22222222-2222-2222-2222-222222222222"
DOC_LOW_CONF_VERIFIED = "33333333-3333-3333-3333-333333333333"


def source(origin: str, page: int = 1) -> dict[str, Any]:
    return {"origin": origin, "page": page, "bbox": [0.1, 0.2, 0.5, 0.24]}


def field(
    value: str | None,
    confidence: float,
    verified: bool,
    gate: str | None = None,
    origin: str = "ocr_latin",
    gate_error: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence,
        "verified": verified,
        "gate": gate,
        "gate_error": gate_error,
        "source": source(origin),
    }


EXTRACTIONS: dict[str, dict[str, Any]] = {
    DOC_FAILED_GATE: {
        "document_id": DOC_FAILED_GATE,
        "extraction_id": "aaaaaaaa-0000-4000-8000-000000000001",
        "pipeline_version": PIPELINE_VERSION,
        "status": "needs_review",
        "document_type": {"value": "invoice", "confidence": 0.97},
        "language": {"primary": "en", "confidence": 0.99},
        "fields": {
            "po_number": field("PO-2291", 0.96, False),
            "customer_name": field("Karachi Textile Mills", 0.94, False),
            "iban": field(
                "PK70BANK0000001234567890",
                0.88,
                False,
                gate="iban_checksum",
                gate_error="mod-97 checksum failed: remainder 87, expected 1",
            ),
            "subtotal": field("25000.00", 0.93, False, gate="line_item_sum"),
            "tax": field("4250.00", 0.91, False, gate="arithmetic_reconciliation"),
            "total": field("29000.00", 0.92, False, gate="arithmetic_reconciliation"),
        },
        "line_items": [
            {
                "description": field("Fibre link 100 Mbps", 0.95, False),
                "quantity": field("2", 0.99, False),
                "unit_price": field("10000.00", 0.94, False),
                "line_total": field("20000.00", 0.94, False),
            },
            {
                "description": field("Installation", 0.93, False),
                "quantity": field("1", 0.99, False),
                "unit_price": field("5000.00", 0.94, False),
                "line_total": field("5000.00", 0.94, False),
            },
        ],
        "gates": [
            {
                "name": "line_item_sum",
                "result": "passed",
                "detail": "2 line items sum to subtotal 25000.00",
                "affected_fields": ["subtotal"],
            },
            {
                "name": "arithmetic_reconciliation",
                "result": "failed",
                "detail": "subtotal 25000.00 + tax 4250.00 = 29250.00, total is 29000.00",
                "affected_fields": ["subtotal", "tax", "total"],
            },
            {
                "name": "iban_checksum",
                "result": "failed",
                "detail": "mod-97 checksum failed: remainder 87, expected 1",
                "affected_fields": ["iban"],
            },
        ],
        "review": {"required": True, "reason": "gate_failed:arithmetic_reconciliation"},
        "timings_ms": {"ocr_latin": 3100, "llm": 41200, "validation": 8, "total": 44308},
        "created_at": "2026-08-04T09:15:00Z",
    },
    DOC_FORMAT_ONLY: {
        "document_id": DOC_FORMAT_ONLY,
        "extraction_id": "aaaaaaaa-0000-4000-8000-000000000002",
        "pipeline_version": PIPELINE_VERSION,
        "status": "needs_review",
        "document_type": {"value": "contract", "confidence": 0.91},
        "language": {"primary": "mixed", "confidence": 0.87},
        "fields": {
            "customer_name": field("لاہور ٹیکسٹائل", 0.79, False, origin="ocr_urdu"),
            "cnic": field("42101-1234567-1", 0.95, False, gate="cnic_format_check"),
            "mrc": field("45000.00", 0.9, False, gate="arithmetic_reconciliation"),
            "otc": field("5000.00", 0.89, False, gate="arithmetic_reconciliation"),
        },
        "line_items": [],
        "gates": [
            {
                "name": "cnic_format_check",
                "result": "format_only",
                "detail": "13 digits, well-formed; CNIC has no checksum so nothing is confirmed",
                "affected_fields": ["cnic"],
            },
            {
                "name": "arithmetic_reconciliation",
                "result": "format_only",
                "detail": (
                    "mrc/otc to total relationship is undetermined: no specified rule "
                    "exists to check them against subtotal or total. See ADR-005"
                ),
                "affected_fields": ["mrc", "otc"],
            },
            {
                "name": "line_item_sum",
                "result": "format_only",
                "detail": "line item sum not computable: line_items absent",
                "affected_fields": ["line_items"],
            },
        ],
        "review": {"required": True, "reason": "format_only:cnic"},
        "timings_ms": {"ocr_latin": 2900, "ocr_urdu": 5100, "llm": 38800, "total": 46800},
        "created_at": "2026-08-04T10:02:00Z",
    },
    DOC_LOW_CONF_VERIFIED: {
        "document_id": DOC_LOW_CONF_VERIFIED,
        "extraction_id": "aaaaaaaa-0000-4000-8000-000000000003",
        "pipeline_version": PIPELINE_VERSION,
        "status": "complete",
        "document_type": {"value": "invoice", "confidence": 0.88},
        "language": {"primary": "en", "confidence": 0.96},
        "fields": {
            "iban": field("PK36SCBL0000001123456702", 0.41, True, gate="iban_checksum"),
            "subtotal": field("10000.00", 0.45, True, gate="line_item_sum"),
            "tax": field("1700.00", 0.52, True, gate="arithmetic_reconciliation"),
            "total": field("11700.00", 0.49, True, gate="arithmetic_reconciliation"),
        },
        "line_items": [
            {
                "description": field("Managed router", 0.44, False),
                "quantity": field("1", 0.98, False),
                "unit_price": field("10000.00", 0.45, False),
                "line_total": field("10000.00", 0.45, False),
            }
        ],
        "gates": [
            {
                "name": "iban_checksum",
                "result": "passed",
                "detail": "mod-97 checksum verified",
                "affected_fields": ["iban"],
            },
            {
                "name": "line_item_sum",
                "result": "passed",
                "detail": "1 line items sum to subtotal 10000.00",
                "affected_fields": ["subtotal"],
            },
            {
                "name": "arithmetic_reconciliation",
                "result": "passed",
                "detail": "subtotal 10000.00 + tax 1700.00 = total 11700.00",
                "affected_fields": ["subtotal", "tax", "total"],
            },
        ],
        "review": {"required": False, "reason": "low_confidence:iban"},
        "timings_ms": {"ocr_latin": 2200, "llm": 30100, "validation": 6, "total": 32306},
        "created_at": "2026-08-04T11:40:00Z",
    },
}

DOCUMENTS: dict[str, dict[str, Any]] = {
    DOC_FAILED_GATE: {
        "filename": "invoice-2291.pdf",
        "status": "needs_review",
        "document_type": "invoice",
        "data_classification": "synthetic",
        "uploaded_at": "2026-08-04T09:14:10Z",
        "needs_review_count": 6,
        "uploaded_monotonic": None,
    },
    DOC_FORMAT_ONLY: {
        "filename": "contract-lahore.pdf",
        "status": "needs_review",
        "document_type": "contract",
        "data_classification": "synthetic",
        "uploaded_at": "2026-08-04T10:01:05Z",
        "needs_review_count": 4,
        "uploaded_monotonic": None,
    },
    DOC_LOW_CONF_VERIFIED: {
        "filename": "invoice-8841.pdf",
        "status": "complete",
        "document_type": "invoice",
        "data_classification": "public",
        "uploaded_at": "2026-08-04T11:39:02Z",
        "needs_review_count": 0,
        "uploaded_monotonic": None,
    },
}
