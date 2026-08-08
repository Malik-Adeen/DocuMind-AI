from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import APPEND_ONLY, IMMUTABLE_DOCUMENT_COLUMNS, Base, Document


class AppendOnlyViolationError(RuntimeError):
    def __init__(self, table: str, operation: str) -> None:
        super().__init__(
            f"INV-4: {table} is append-only; {operation} is not a permitted operation. "
            "Record a new row instead — the audit trail is the product."
        )
        self.table = table
        self.operation = operation


class ImmutableColumnError(RuntimeError):
    def __init__(self, column: str) -> None:
        super().__init__(
            f"INV-3/INV-6: documents.{column} is set at upload and immutable. "
            "Reclassifying or re-storing a document creates a new document row."
        )
        self.column = column


def _table_of(instance: Base) -> str:
    return str(getattr(type(instance), "__tablename__", type(instance).__name__))


def _refuse_immutable_document_columns(document: Document) -> None:
    attributes = inspect(document).attrs
    for column in IMMUTABLE_DOCUMENT_COLUMNS:
        if attributes[column].history.has_changes():
            raise ImmutableColumnError(column)


@event.listens_for(Session, "before_flush")
def _refuse_mutation_of_append_only_rows(
    session: Session,
    flush_context: object,
    instances: object,
) -> None:
    for instance in session.dirty:
        if isinstance(instance, APPEND_ONLY) and session.is_modified(instance):
            raise AppendOnlyViolationError(_table_of(instance), "UPDATE")
        if isinstance(instance, Document):
            _refuse_immutable_document_columns(instance)

    for instance in session.deleted:
        if isinstance(instance, APPEND_ONLY):
            raise AppendOnlyViolationError(_table_of(instance), "DELETE")


@lru_cache
def get_engine() -> Engine:
    from app.core.config import get_settings

    return create_engine(get_settings().database_url, pool_pre_ping=True, future=True)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
