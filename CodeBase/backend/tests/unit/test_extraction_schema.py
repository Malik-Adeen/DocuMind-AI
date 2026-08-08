from __future__ import annotations

from jsonschema import Draft202012Validator

from app.schemas.extraction import extraction_schema, model_output_schema


def test_model_output_schema_reuses_the_same_defs_as_the_full_schema() -> None:
    derived = model_output_schema()
    full = extraction_schema()

    assert derived["$defs"] == full["$defs"]


def test_model_output_schema_only_requires_document_type_and_fields() -> None:
    derived = model_output_schema()

    assert derived["required"] == ["document_type", "fields"]
    assert derived["additionalProperties"] is False
    assert set(derived["properties"]) == {"document_type", "language", "fields", "line_items"}


def test_model_output_schema_accepts_a_minimal_valid_payload() -> None:
    Draft202012Validator(model_output_schema()).validate(
        {
            "document_type": {"value": "invoice", "confidence": 0.9},
            "fields": {
                "po_number": {
                    "value": "PO-1",
                    "confidence": 0.9,
                    "verified": False,
                    "source": {"origin": "llm_inferred"},
                }
            },
        }
    )


def test_model_output_schema_rejects_a_field_missing_source() -> None:
    validator = Draft202012Validator(model_output_schema())
    errors = list(
        validator.iter_errors(
            {
                "document_type": {"value": "invoice", "confidence": 0.9},
                "fields": {"po_number": {"value": "PO-1", "confidence": 0.9, "verified": False}},
            }
        )
    )
    assert errors
