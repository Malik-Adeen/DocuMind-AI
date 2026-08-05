from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import Float, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AuditLog, Base, Correction, Document, Extraction
from app.db.queries import current_extraction, unverified_field_counts
from app.db.session import AppendOnlyViolationError, ImmutableColumnError, get_engine
from tests.integration.conftest import PIPELINE_VERSION, extraction_result, field

pytestmark = pytest.mark.integration

APPEND_ONLY_TABLES = ("extractions", "corrections", "audit_log")


def add_extraction(
    session: Session,
    document_id: uuid.UUID,
    result: dict[str, Any] | None = None,
    pipeline_version: dict[str, Any] | None = None,
) -> uuid.UUID:
    extraction = Extraction(
        id=uuid.uuid4(),
        document_id=document_id,
        pipeline_version=pipeline_version or PIPELINE_VERSION,
        result=result if result is not None else extraction_result(document_id),
        status="needs_review",
    )
    session.add(extraction)
    session.commit()
    return extraction.id


def add_correction(
    session: Session,
    extraction_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    name: str,
    value: str | None,
) -> None:
    session.add(
        Correction(
            id=uuid.uuid4(),
            extraction_id=extraction_id,
            field=name,
            value=value,
            corrected_by=reviewer_id,
        )
    )
    session.commit()


# ---------------------------------------------------------------- INV-4, at the DB


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_update_is_refused_by_the_database(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID, table: str
) -> None:
    extraction_id = add_extraction(session, document_id)
    add_correction(session, extraction_id, reviewer_id, "total", "1.00")
    session.execute(
        text("INSERT INTO audit_log (action, entity, entity_id) VALUES ('x', 'y', 'z')")
    )
    session.commit()

    with pytest.raises(IntegrityError, match="append-only"):
        session.execute(text(f"UPDATE {table} SET created_at = now()"))
    session.rollback()


@pytest.mark.parametrize("table", APPEND_ONLY_TABLES)
def test_delete_is_refused_by_the_database(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID, table: str
) -> None:
    extraction_id = add_extraction(session, document_id)
    add_correction(session, extraction_id, reviewer_id, "total", "1.00")
    session.execute(
        text("INSERT INTO audit_log (action, entity, entity_id) VALUES ('x', 'y', 'z')")
    )
    session.commit()

    with pytest.raises(IntegrityError, match="append-only"):
        session.execute(text(f"DELETE FROM {table}"))
    session.rollback()


def test_the_trigger_names_the_invariant_it_is_protecting(
    session: Session, document_id: uuid.UUID
) -> None:
    add_extraction(session, document_id)
    with pytest.raises(IntegrityError, match="INV-4"):
        session.execute(text("UPDATE extractions SET status = 'complete'"))
    session.rollback()


# ---------------------------------------------------------------- INV-4, in the code


def test_orm_update_of_an_extraction_is_refused_before_it_reaches_the_database(
    session: Session, document_id: uuid.UUID
) -> None:
    extraction_id = add_extraction(session, document_id)
    extraction = session.get(Extraction, extraction_id)
    assert extraction is not None

    extraction.status = "complete"
    with pytest.raises(AppendOnlyViolationError) as caught:
        session.commit()
    assert caught.value.table == "extractions"
    assert caught.value.operation == "UPDATE"
    session.rollback()


def test_orm_delete_of_a_correction_is_refused_before_it_reaches_the_database(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    extraction_id = add_extraction(session, document_id)
    add_correction(session, extraction_id, reviewer_id, "total", "1.00")
    correction = session.query(Correction).one()

    session.delete(correction)
    with pytest.raises(AppendOnlyViolationError) as caught:
        session.commit()
    assert caught.value.operation == "DELETE"
    session.rollback()


def test_orm_delete_of_an_audit_row_is_refused(session: Session) -> None:
    entry = AuditLog(action="upload", entity="document", entity_id="1")
    session.add(entry)
    session.commit()

    session.delete(entry)
    with pytest.raises(AppendOnlyViolationError):
        session.commit()
    session.rollback()


def test_re_running_the_same_pipeline_version_inserts_a_second_row(
    session: Session, document_id: uuid.UUID
) -> None:
    first = add_extraction(session, document_id)
    second = add_extraction(session, document_id)

    assert first != second
    rows = session.query(Extraction).filter_by(document_id=document_id).all()
    assert len(rows) == 2, "INV-4 says re-running produces a new row, not an overwrite"
    assert {row.pipeline_version["prompt_hash"] for row in rows} == {"sha256:2f1a9c"}


# ---------------------------------------------------------------- INV-6 / INV-3 immutability


def test_reclassification_is_refused_by_the_database(
    session: Session, document_id: uuid.UUID
) -> None:
    with pytest.raises(IntegrityError, match="INV-6"):
        session.execute(
            text("UPDATE documents SET data_classification = 'public' WHERE id = :id"),
            {"id": document_id},
        )
    session.rollback()

    stored = session.execute(
        text("SELECT data_classification FROM documents WHERE id = :id"), {"id": document_id}
    ).scalar()
    assert stored == "synthetic"


@pytest.mark.parametrize(
    ("column", "value", "invariant"),
    [
        ("storage_path", "var/uploads/elsewhere.pdf", "INV-3"),
        ("sha256", "b" * 64, "INV-3"),
    ],
)
def test_the_raw_upload_pointer_is_refused_by_the_database(
    session: Session, document_id: uuid.UUID, column: str, value: str, invariant: str
) -> None:
    with pytest.raises(IntegrityError, match=invariant):
        session.execute(
            text(f"UPDATE documents SET {column} = :value WHERE id = :id"),
            {"value": value, "id": document_id},
        )
    session.rollback()


def test_orm_reclassification_is_refused_before_it_reaches_the_database(
    session: Session, document_id: uuid.UUID
) -> None:
    document = session.get(Document, document_id)
    assert document is not None

    document.data_classification = "public"
    with pytest.raises(ImmutableColumnError) as caught:
        session.commit()
    assert caught.value.column == "data_classification"
    session.rollback()


def test_status_is_still_updatable_on_a_document(session: Session, document_id: uuid.UUID) -> None:
    document = session.get(Document, document_id)
    assert document is not None

    document.status = "complete"
    session.commit()

    session.expire_all()
    refreshed = session.get(Document, document_id)
    assert refreshed is not None
    assert refreshed.status == "complete"
    assert refreshed.data_classification == "synthetic"


def test_an_unrecognised_classification_cannot_be_inserted(session: Session) -> None:
    with pytest.raises(Exception, match="documents_classification_valid"):
        session.execute(
            text(
                "INSERT INTO documents "
                "(id, filename, storage_path, content_type, byte_size, sha256, "
                " data_classification, status, document_type) "
                "VALUES (gen_random_uuid(), 'x.pdf', 'p', 'application/pdf', 1, "
                f"'{'a' * 64}', 'customer', 'queued', 'invoice')"
            )
        )
    session.rollback()


# ---------------------------------------------------------------- money


def test_no_column_anywhere_is_a_float() -> None:
    offenders = [
        f"{table.name}.{column.name} is {column.type}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, Float)
    ]
    assert not offenders, f"money must never touch binary floating point: {offenders}"


def test_a_numeric_field_value_is_refused_by_the_database(
    session: Session, document_id: uuid.UUID
) -> None:
    result = extraction_result(document_id, total=field(None))
    result["fields"]["total"]["value"] = 11700.00

    with pytest.raises(Exception, match="never_numeric"):
        add_extraction(session, document_id, result=result)
    session.rollback()


def test_a_numeric_line_item_value_is_refused_by_the_database(
    session: Session, document_id: uuid.UUID
) -> None:
    result = extraction_result(document_id)
    result["line_items"] = [{"line_total": {**field(None), "value": 20000.0}}]

    with pytest.raises(Exception, match="never_numeric"):
        add_extraction(session, document_id, result=result)
    session.rollback()


def test_a_decimal_string_survives_the_round_trip_exactly(
    session: Session, document_id: uuid.UUID
) -> None:
    result = extraction_result(
        document_id,
        total=field("11700.00"),
        mrc=field("45000.50"),
        tax=field("-0.05"),
    )
    add_extraction(session, document_id, result=result)

    stored = current_extraction(session, document_id)
    assert stored is not None
    assert stored["fields"]["total"]["value"] == "11700.00"
    assert stored["fields"]["mrc"]["value"] == "45000.50"
    assert stored["fields"]["tax"]["value"] == "-0.05"


# ---------------------------------------------------------------- pipeline_version


def test_pipeline_version_must_carry_a_profile(session: Session, document_id: uuid.UUID) -> None:
    unprofiled = {k: v for k, v in PIPELINE_VERSION.items() if k != "profile"}
    with pytest.raises(Exception, match="pipeline_version_shaped"):
        add_extraction(session, document_id, pipeline_version=unprofiled)
    session.rollback()


def test_an_unknown_profile_is_refused(session: Session, document_id: uuid.UUID) -> None:
    with pytest.raises(Exception, match="profile_valid"):
        add_extraction(
            session, document_id, pipeline_version={**PIPELINE_VERSION, "profile": "staging"}
        )
    session.rollback()


def test_a_stale_schema_version_is_refused(session: Session, document_id: uuid.UUID) -> None:
    with pytest.raises(Exception, match="schema_version_current"):
        add_extraction(
            session, document_id, pipeline_version={**PIPELINE_VERSION, "schema_version": "0.2.0"}
        )
    session.rollback()


def test_pipeline_version_is_stored_as_jsonb_not_text(session: Session) -> None:
    kind = session.execute(
        text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'extractions' AND column_name = 'pipeline_version'"
        )
    ).scalar()
    assert kind == "jsonb"


# ---------------------------------------------------------------- the current view


def test_current_view_without_corrections_is_the_extraction_itself(
    session: Session, document_id: uuid.UUID
) -> None:
    result = extraction_result(document_id, total=field("29000.00"), po_number=field("PO-2291"))
    add_extraction(session, document_id, result=result)

    view = current_extraction(session, document_id)
    assert view is not None
    assert view["fields"]["total"] == result["fields"]["total"]
    assert view["fields"]["po_number"] == result["fields"]["po_number"]


def test_current_view_applies_a_correction(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    result = extraction_result(document_id, total=field("29000.00"))
    extraction_id = add_extraction(session, document_id, result=result)
    add_correction(session, extraction_id, reviewer_id, "total", "29250.00")

    view = current_extraction(session, document_id)
    assert view is not None
    total = view["fields"]["total"]
    assert total["value"] == "29250.00"
    assert total["verified"] is True
    assert total["gate"] is None
    assert total["gate_error"] is None
    assert total["source"] == {"origin": "human"}


def test_current_view_takes_the_latest_correction_for_a_field(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    extraction_id = add_extraction(
        session, document_id, result=extraction_result(document_id, total=field("1.00"))
    )
    add_correction(session, extraction_id, reviewer_id, "total", "2.00")
    add_correction(session, extraction_id, reviewer_id, "total", "3.00")

    view = current_extraction(session, document_id)
    assert view is not None
    assert view["fields"]["total"]["value"] == "3.00"


def test_current_view_leaves_uncorrected_fields_alone(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    result = extraction_result(
        document_id, total=field("1.00"), po_number=field("PO-2291", confidence=0.96)
    )
    extraction_id = add_extraction(session, document_id, result=result)
    add_correction(session, extraction_id, reviewer_id, "total", "2.00")

    view = current_extraction(session, document_id)
    assert view is not None
    assert view["fields"]["po_number"]["value"] == "PO-2291"
    assert view["fields"]["po_number"]["verified"] is False
    assert view["fields"]["po_number"]["source"]["origin"] == "ocr_latin"


def test_current_view_adds_a_field_the_extraction_never_produced(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    extraction_id = add_extraction(session, document_id, result=extraction_result(document_id))
    add_correction(session, extraction_id, reviewer_id, "iban", "PK36SCBL0000001123456702")

    view = current_extraction(session, document_id)
    assert view is not None
    iban = view["fields"]["iban"]
    assert iban["value"] == "PK36SCBL0000001123456702"
    assert iban["verified"] is True
    assert iban["confidence"] == 0.0
    assert iban["source"] == {"origin": "human"}


def test_current_view_uses_only_the_latest_extraction(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    old = add_extraction(
        session, document_id, result=extraction_result(document_id, total=field("1.00"))
    )
    add_correction(session, extraction_id=old, reviewer_id=reviewer_id, name="total", value="2.00")
    add_extraction(
        session, document_id, result=extraction_result(document_id, total=field("500.00"))
    )

    view = current_extraction(session, document_id)
    assert view is not None
    assert view["fields"]["total"]["value"] == "500.00", (
        "a correction on a superseded extraction leaked into the current view"
    )
    assert view["fields"]["total"]["verified"] is False


def test_latest_is_decided_by_seq_not_by_a_timestamp_that_can_tie(
    session: Session, document_id: uuid.UUID
) -> None:
    add_extraction(session, document_id, result=extraction_result(document_id, total=field("1.00")))
    add_extraction(session, document_id, result=extraction_result(document_id, total=field("2.00")))
    session.execute(
        text("UPDATE documents SET status = 'complete' WHERE id = :id"), {"id": document_id}
    )
    session.commit()

    rows = session.execute(text("SELECT seq, created_at FROM extractions ORDER BY seq")).all()
    assert [row.seq for row in rows] == sorted(row.seq for row in rows)
    assert len({row.seq for row in rows}) == 2, "seq must be monotonic and unique"

    for _ in range(5):
        view = current_extraction(session, document_id)
        assert view is not None
        assert view["fields"]["total"]["value"] == "2.00"


def test_current_view_of_an_unknown_document_is_none(session: Session) -> None:
    assert current_extraction(session, uuid.uuid4()) is None


def test_current_view_of_a_document_with_no_extraction_is_none(
    session: Session, document_id: uuid.UUID
) -> None:
    assert current_extraction(session, document_id) is None


def test_current_view_is_a_single_statement() -> None:
    from app.db.queries import CURRENT_EXTRACTION_VIEW

    body = str(CURRENT_EXTRACTION_VIEW).strip().rstrip(";")
    assert ";" not in body, "the current view must be one query, not a script"


def test_unverified_counts_ignore_corrected_fields(
    session: Session, document_id: uuid.UUID, reviewer_id: uuid.UUID
) -> None:
    result = extraction_result(
        document_id,
        total=field("1.00"),
        po_number=field("PO-2291"),
        iban=field("PK36", verified=True),
    )
    extraction_id = add_extraction(session, document_id, result=result)
    assert unverified_field_counts(session, [document_id]) == {document_id: 2}

    add_correction(session, extraction_id, reviewer_id, "total", "2.00")
    assert unverified_field_counts(session, [document_id]) == {document_id: 1}


def test_unverified_counts_of_nothing_is_empty(session: Session) -> None:
    assert unverified_field_counts(session, []) == {}


# ---------------------------------------------------------------- models match the migration


def test_models_and_migration_have_not_drifted(database: str) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    with get_engine().connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)

    ignorable = {"add_table", "remove_table"}
    real = [
        entry for entry in diff if entry[0] not in ignorable or entry[1].name != "alembic_version"
    ]  # type: ignore[union-attr]
    assert not real, f"app/db/models.py and the migration disagree: {real}"
