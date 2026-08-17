"""schema_version 0.3.1: source.unmatched marks a claimed-but-unresolved provenance quote

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-17

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("extractions_schema_version_current", "extractions", type_="check")
    op.create_check_constraint(
        "extractions_schema_version_current",
        "extractions",
        "pipeline_version ->> 'schema_version' = '0.3.1'",
    )


def downgrade() -> None:
    op.drop_constraint("extractions_schema_version_current", "extractions", type_="check")
    op.create_check_constraint(
        "extractions_schema_version_current",
        "extractions",
        "pipeline_version ->> 'schema_version' = '0.3.0'",
    )
