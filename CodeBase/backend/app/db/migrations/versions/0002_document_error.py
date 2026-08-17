"""documents.error: populated cause for a subset of extraction failures

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-14

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("error", postgresql.JSONB(), nullable=True))
    op.create_check_constraint(
        "documents_error_shaped",
        "documents",
        "error IS NULL OR (error ? 'code' AND error ? 'message' AND error ? 'retryable')",
    )


def downgrade() -> None:
    op.drop_constraint("documents_error_shaped", "documents", type_="check")
    op.drop_column("documents", "error")
