"""Danny's D-78: files pinned to a cash drawer session at close.

One new table, `cash_drawer_attachments`, the same shape as
`expense_attachments` (bytes in `media_files`). **Nothing existing is altered
and no existing row is touched**, so this is safe on a live tenant mid-service.
The close note needs no migration: `cash_drawer_sessions.note` already exists.

🔴 Chained on `c3d4e5f6a7b8`. The uncommitted Meta Pixel migration
`b0c1d2e3f4a5` in the working tree must now revise THIS revision when it ships,
or alembic will see two heads.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_drawer_attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["session_id"], ["cash_drawer_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cash_drawer_attachments_tenant_id", "cash_drawer_attachments", ["tenant_id"]
    )
    op.create_index(
        "ix_cash_drawer_attachment_session", "cash_drawer_attachments", ["session_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_cash_drawer_attachment_session", table_name="cash_drawer_attachments")
    op.drop_index("ix_cash_drawer_attachments_tenant_id", table_name="cash_drawer_attachments")
    op.drop_table("cash_drawer_attachments")
