from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum


class DataClassification(StrEnum):
    PUBLIC = "public"
    SYNTHETIC = "synthetic"
    RESTRICTED = "restricted"


def classify(raw: object) -> DataClassification:
    if isinstance(raw, str):
        try:
            return DataClassification(raw.strip().lower())
        except ValueError:
            return DataClassification.RESTRICTED
    return DataClassification.RESTRICTED


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    document_id: str
    filename: str
    data_classification: DataClassification = DataClassification.RESTRICTED
    uploaded_at: str | None = None
    storage_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_classification", classify(self.data_classification))


def reclassify(
    record: DocumentRecord,
    classification: object,
    *,
    document_id: str,
) -> DocumentRecord:
    if document_id == record.document_id:
        raise ValueError(
            f"INV-3: document {record.document_id} cannot be reclassified in place. "
            "Reclassification is a new document record with a new document_id, never an UPDATE."
        )
    return replace(
        record,
        document_id=document_id,
        data_classification=classify(classification),
    )
