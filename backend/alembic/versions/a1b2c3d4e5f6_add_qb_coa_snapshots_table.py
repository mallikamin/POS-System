"""add_qb_coa_snapshots_table

Revision ID: a1b2c3d4e5f6
Revises: 0ac2200039d0
Create Date: 2026-02-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str = '0ac2200039d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'qb_coa_snapshots',
        sa.Column('id', sa.Uuid(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('connection_id', sa.Uuid(), nullable=False),
        sa.Column('snapshot_type', sa.String(20), nullable=False, comment='original_backup | working_copy'),
        sa.Column('coa_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Full array of QB account objects at time of snapshot'),
        sa.Column('account_count', sa.Integer(), nullable=False, default=0),
        sa.Column('is_locked', sa.Boolean(), nullable=False, default=False, comment='True for original_backup — prevents edits'),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False, comment='When the CoA was fetched from QB API'),
        sa.Column('qb_company_name', sa.String(255), nullable=False, comment='Company name at time of snapshot'),
        sa.Column('qb_realm_id', sa.String(50), nullable=False, comment='QB company ID at time of snapshot'),
        sa.Column('notes', sa.String(500), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1, comment='Tracks re-fetch count'),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['connection_id'], ['qb_connections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_qbcoa_tenant_conn_type',
        'qb_coa_snapshots',
        ['tenant_id', 'connection_id', 'snapshot_type'],
    )
    op.create_index(
        'ix_qbcoa_tenant_id',
        'qb_coa_snapshots',
        ['tenant_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_qbcoa_tenant_id', table_name='qb_coa_snapshots')
    op.drop_index('ix_qbcoa_tenant_conn_type', table_name='qb_coa_snapshots')
    op.drop_table('qb_coa_snapshots')
