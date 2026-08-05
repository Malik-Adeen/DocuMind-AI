"""initial schema: documents, extractions, corrections, exports, users, audit_log

Revision ID: 0001
Revises:
Create Date: 2026-08-05

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = ("extractions", "corrections", "audit_log")

REFUSE_MUTATION = """
CREATE OR REPLACE FUNCTION refuse_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'INV-4: %.% is append-only; % is not permitted. Insert a new row instead.',
        TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""

REFUSE_DOCUMENT_REWRITE = """
CREATE OR REPLACE FUNCTION refuse_document_rewrite() RETURNS trigger AS $$
BEGIN
    IF NEW.data_classification IS DISTINCT FROM OLD.data_classification THEN
        RAISE EXCEPTION
            'INV-6: documents.data_classification is set at upload and immutable (% -> %). '
            'Reclassification is a new document, not an UPDATE.',
            OLD.data_classification, NEW.data_classification
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.storage_path IS DISTINCT FROM OLD.storage_path THEN
        RAISE EXCEPTION
            'INV-3: documents.storage_path is immutable; the raw upload is never rewritten.'
            USING ERRCODE = 'restrict_violation';
    END IF;
    IF NEW.sha256 IS DISTINCT FROM OLD.sha256 THEN
        RAISE EXCEPTION
            'INV-3: documents.sha256 is immutable; it is the fingerprint of the raw upload.'
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("role IN ('viewer', 'reviewer', 'admin')", name="users_role_valid"),
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data_classification", sa.Text(), nullable=False, server_default="restricted"),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("document_type", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column(
            "uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "data_classification IN ('public', 'synthetic', 'restricted')",
            name="documents_classification_valid",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'ocr', 'extracting', 'validating', 'needs_review', "
            "'complete', 'failed')",
            name="documents_status_valid",
        ),
        sa.CheckConstraint(
            "document_type IN ('invoice', 'purchase_order', 'contract', 'quotation', "
            "'billing_sheet', 'unknown')",
            name="documents_type_valid",
        ),
        sa.CheckConstraint("byte_size >= 0", name="documents_byte_size_non_negative"),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_uploaded_at", "documents", ["uploaded_at"])

    op.create_table(
        "extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("pipeline_version", postgresql.JSONB(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('complete', 'needs_review', 'failed')", name="extractions_status_valid"
        ),
        sa.CheckConstraint(
            "pipeline_version ? 'profile' AND pipeline_version ? 'prompt_hash'",
            name="extractions_pipeline_version_shaped",
        ),
        sa.CheckConstraint(
            "pipeline_version ->> 'profile' IN ('prototype', 'production')",
            name="extractions_profile_valid",
        ),
        sa.CheckConstraint(
            "pipeline_version ->> 'schema_version' = '0.3.0'",
            name="extractions_schema_version_current",
        ),
        sa.CheckConstraint(
            "NOT jsonb_path_exists(result, '$.fields.*.value ? (@.type() == \"number\")')",
            name="extractions_field_values_never_numeric",
        ),
        sa.CheckConstraint(
            "NOT jsonb_path_exists(result, '$.line_items[*].*.value ? (@.type() == \"number\")')",
            name="extractions_line_item_values_never_numeric",
        ),
    )
    op.create_index("ix_extractions_document_seq", "extractions", ["document_id", "seq"])

    op.create_table(
        "corrections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column(
            "extraction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extractions.id"),
            nullable=False,
        ),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "corrected_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_corrections_extraction_field",
        "corrections",
        ["extraction_id", "field", "seq"],
    )

    op.create_table(
        "exports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("document_ids", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "requested_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("format IN ('xlsx', 'csv', 'json')", name="exports_format_valid"),
        sa.CheckConstraint(
            "status IN ('queued', 'complete', 'failed')", name="exports_status_valid"
        ),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity", "entity_id"])

    op.execute(REFUSE_MUTATION)
    for table in APPEND_ONLY_TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_append_only "
            f"BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION refuse_mutation()"
        )

    op.execute(REFUSE_DOCUMENT_REWRITE)
    op.execute(
        "CREATE TRIGGER documents_immutable_columns "
        "BEFORE UPDATE ON documents "
        "FOR EACH ROW EXECUTE FUNCTION refuse_document_rewrite()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS documents_immutable_columns ON documents")
    op.execute("DROP FUNCTION IF EXISTS refuse_document_rewrite()")
    for table in APPEND_ONLY_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS refuse_mutation()")

    op.drop_table("audit_log")
    op.drop_table("exports")
    op.drop_table("corrections")
    op.drop_table("extractions")
    op.drop_table("documents")
    op.drop_table("users")
