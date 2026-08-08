from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CLASSIFICATIONS = ("public", "synthetic", "restricted")
DOCUMENT_STATUSES = (
    "queued",
    "ocr",
    "extracting",
    "validating",
    "needs_review",
    "complete",
    "failed",
)
DOCUMENT_TYPES = (
    "invoice",
    "purchase_order",
    "contract",
    "quotation",
    "billing_sheet",
    "unknown",
)
EXTRACTION_STATUSES = ("complete", "needs_review", "failed")
EXPORT_FORMATS = ("xlsx", "csv", "json")
EXPORT_STATUSES = ("queued", "complete", "failed")
PROFILES = ("prototype", "production")
ROLES = ("viewer", "reviewer", "admin")
SCHEMA_VERSION = "0.3.0"


def _one_of(column: str, allowed: tuple[str, ...]) -> str:
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


class Base(DeclarativeBase):
    pass


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _pk()
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (CheckConstraint(_one_of("role", ROLES), name="users_role_valid"),)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _pk()
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    data_classification: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="restricted"
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    document_type: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    uploaded_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint(
            _one_of("data_classification", CLASSIFICATIONS),
            name="documents_classification_valid",
        ),
        CheckConstraint(_one_of("status", DOCUMENT_STATUSES), name="documents_status_valid"),
        CheckConstraint(_one_of("document_type", DOCUMENT_TYPES), name="documents_type_valid"),
        CheckConstraint("byte_size >= 0", name="documents_byte_size_non_negative"),
        Index("ix_documents_status", "status"),
        Index("ix_documents_uploaded_at", "uploaded_at"),
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = _pk()
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    pipeline_version: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint(_one_of("status", EXTRACTION_STATUSES), name="extractions_status_valid"),
        CheckConstraint(
            "pipeline_version ? 'profile' AND pipeline_version ? 'prompt_hash'",
            name="extractions_pipeline_version_shaped",
        ),
        CheckConstraint(
            "pipeline_version ->> 'profile' IN ('prototype', 'production')",
            name="extractions_profile_valid",
        ),
        CheckConstraint(
            f"pipeline_version ->> 'schema_version' = '{SCHEMA_VERSION}'",
            name="extractions_schema_version_current",
        ),
        CheckConstraint(
            "NOT jsonb_path_exists(result, '$.fields.*.value ? (@.type() == \"number\")')",
            name="extractions_field_values_never_numeric",
        ),
        CheckConstraint(
            "NOT jsonb_path_exists(result, '$.line_items[*].*.value ? (@.type() == \"number\")')",
            name="extractions_line_item_values_never_numeric",
        ),
        Index("ix_extractions_document_seq", "document_id", "seq"),
    )


class Correction(Base):
    __tablename__ = "corrections"

    id: Mapped[uuid.UUID] = _pk()
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True)
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extractions.id"), nullable=False
    )
    field: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("ix_corrections_extraction_field", "extraction_id", "field", "seq"),)


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = _pk()
    format: Mapped[str] = mapped_column(Text, nullable=False)
    document_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (
        CheckConstraint(_one_of("format", EXPORT_FORMATS), name="exports_format_valid"),
        CheckConstraint(_one_of("status", EXPORT_STATUSES), name="exports_status_valid"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = _created_at()

    __table_args__ = (Index("ix_audit_log_entity", "entity", "entity_id"),)


APPEND_ONLY: tuple[type[Base], ...] = (Extraction, Correction, AuditLog)

IMMUTABLE_DOCUMENT_COLUMNS = ("data_classification", "storage_path", "sha256")
