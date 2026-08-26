"""AI usage log: one row per model call, with tokens and estimated cost.

Revision ID: z2a3b4c5d6e7
Revises: y1z2a3b4c5d6
Create Date: 2026-08-26

Why this exists
----------------
Two optional AI features are being added (OCR goods receiving, and the ordering
advisor). The `api-cost-playbook` puts instrumentation at step 1 of its
checklist, ahead of the features themselves: unmeasured model spend is the
failure mode it exists to prevent, and on the project it was distilled from the
first usage numbers undercounted by ~83% because one call path was not logged.

This table is what makes the per-tenant daily caps enforceable and the spend
reconcilable against the Anthropic console.

Safety
------
🟢 One new table. Nothing existing is altered, and a deployment with no API key
never writes a row to it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "z2a3b4c5d6e7"
down_revision: str | None = "y1z2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=60), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column(
            "input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "cache_creation_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cache_read_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "estimated_cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "succeeded", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_usage_log_tenant_id", "ai_usage_log", ["tenant_id"])
    op.create_index(
        "ix_ai_usage_tenant_day", "ai_usage_log", ["tenant_id", "usage_date"]
    )
    op.create_index("ix_ai_usage_kind", "ai_usage_log", ["tenant_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_kind", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_tenant_day", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_tenant_id", table_name="ai_usage_log")
    op.drop_table("ai_usage_log")
