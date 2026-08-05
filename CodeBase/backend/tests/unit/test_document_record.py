from __future__ import annotations

import dataclasses

import pytest

from app.db.documents import (
    DataClassification,
    DocumentRecord,
    classify,
    reclassify,
)

DOC = "doc-4471"
OTHER = "doc-4472"


def record(classification: object = DataClassification.SYNTHETIC) -> DocumentRecord:
    return DocumentRecord(
        document_id=DOC,
        filename="invoice-2291.pdf",
        data_classification=classification,  # type: ignore[arg-type]
        uploaded_at="2026-08-05T09:00:00Z",
    )


def test_classification_is_recorded_at_upload() -> None:
    assert record("public").data_classification is DataClassification.PUBLIC


def test_assigning_the_classification_is_rejected() -> None:
    document = record("synthetic")
    with pytest.raises(dataclasses.FrozenInstanceError):
        document.data_classification = DataClassification.PUBLIC  # type: ignore[misc]
    assert document.data_classification is DataClassification.SYNTHETIC


@pytest.mark.parametrize("field", ["document_id", "filename", "uploaded_at"])
def test_the_whole_record_is_immutable_not_just_the_classification(field: str) -> None:
    document = record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(document, field, "x")


def test_deleting_the_classification_is_rejected() -> None:
    document = record()
    with pytest.raises(dataclasses.FrozenInstanceError):
        del document.data_classification  # type: ignore[misc]


def test_default_is_restricted() -> None:
    document = DocumentRecord(document_id=DOC, filename="scan.pdf")
    assert document.data_classification is DataClassification.RESTRICTED


@pytest.mark.parametrize(
    "raw",
    [None, "", "   ", "customer", "unknown", "internal", "confidential", 0, 1, True, object(), []],
)
def test_missing_or_unrecognised_is_restricted(raw: object) -> None:
    assert record(raw).data_classification is DataClassification.RESTRICTED


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("PUBLIC", DataClassification.PUBLIC),
        (" public ", DataClassification.PUBLIC),
        ("Synthetic", DataClassification.SYNTHETIC),
        ("RESTRICTED", DataClassification.RESTRICTED),
    ],
)
def test_classification_is_case_and_whitespace_insensitive(
    raw: str, expected: DataClassification
) -> None:
    assert record(raw).data_classification is expected


def test_classify_defaults_to_restricted_rather_than_returning_nothing() -> None:
    assert classify("public") is DataClassification.PUBLIC
    assert classify(DataClassification.SYNTHETIC) is DataClassification.SYNTHETIC
    assert classify("confidential") is DataClassification.RESTRICTED
    assert classify(None) is DataClassification.RESTRICTED
    assert classify(42) is DataClassification.RESTRICTED


def test_reclassification_is_a_new_document() -> None:
    original = record("restricted")
    relabelled = reclassify(original, "synthetic", document_id=OTHER)

    assert relabelled.document_id == OTHER
    assert relabelled.data_classification is DataClassification.SYNTHETIC
    assert original.document_id == DOC
    assert original.data_classification is DataClassification.RESTRICTED


def test_reclassification_in_place_is_rejected() -> None:
    original = record("restricted")
    with pytest.raises(ValueError, match="never an UPDATE"):
        reclassify(original, "public", document_id=DOC)
    assert original.data_classification is DataClassification.RESTRICTED


def test_reclassification_to_an_unrecognised_value_is_restricted() -> None:
    relabelled = reclassify(record("public"), "confidential", document_id=OTHER)
    assert relabelled.data_classification is DataClassification.RESTRICTED
