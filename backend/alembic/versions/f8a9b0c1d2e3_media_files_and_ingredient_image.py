"""media_files table + ingredients.image_url

Photographs for menu items and ingredients, uploaded from the admin forms.

`media_files` holds the normalised JPEG bytes (see app/models/media.py for why
the database rather than a disk path). `ingredients.image_url` mirrors the
`menu_items.image_url` column that has existed since phase 3: nullable, and
NULL for every existing row, so no screen changes until a photo is uploaded.

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_files_tenant_id", "media_files", ["tenant_id"])

    op.add_column(
        "ingredients",
        sa.Column("image_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingredients", "image_url")
    op.drop_index("ix_media_files_tenant_id", table_name="media_files")
    op.drop_table("media_files")
