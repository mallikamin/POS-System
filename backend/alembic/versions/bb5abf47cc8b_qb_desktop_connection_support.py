"""qb_desktop_connection_support

Revision ID: bb5abf47cc8b
Revises: l8m9n0o1p2q3
Create Date: 2026-03-25 14:49:47.311059

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb5abf47cc8b'
down_revision: Union[str, None] = 'l8m9n0o1p2q3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for connection_type
    connection_type_enum = sa.Enum('online', 'desktop', name='qb_connection_type')
    connection_type_enum.create(op.get_bind(), checkfirst=True)

    # Add new columns to qb_connections table
    op.add_column('qb_connections', sa.Column('connection_type', connection_type_enum, nullable=False, server_default='online'))
    op.add_column('qb_connections', sa.Column('qbwc_username', sa.String(100), nullable=True))
    op.add_column('qb_connections', sa.Column('qbwc_password_encrypted', sa.Text, nullable=True))
    op.add_column('qb_connections', sa.Column('qb_desktop_version', sa.String(50), nullable=True, comment='QB Desktop version, e.g. "Enterprise 2024"'))
    op.add_column('qb_connections', sa.Column('company_file_path', sa.String(500), nullable=True, comment='QB Desktop company file path'))
    op.add_column('qb_connections', sa.Column('last_qbwc_poll_at', sa.DateTime(timezone=True), nullable=True, comment='Last time QBWC polled for requests'))

    # Make OAuth fields nullable (Desktop doesn't use them)
    op.alter_column('qb_connections', 'realm_id', nullable=True)
    op.alter_column('qb_connections', 'access_token_encrypted', nullable=True)
    op.alter_column('qb_connections', 'refresh_token_encrypted', nullable=True)
    op.alter_column('qb_connections', 'access_token_expires_at', nullable=True)
    op.alter_column('qb_connections', 'refresh_token_expires_at', nullable=True)

    # Add index for QBWC username lookup
    op.create_index('ix_qbconn_qbwc_username', 'qb_connections', ['qbwc_username'], unique=False)

    # Add fields to qb_sync_queue for Desktop XML storage
    op.add_column('qb_sync_queue', sa.Column('request_xml', sa.Text, nullable=True, comment='QBXML request for Desktop'))
    op.add_column('qb_sync_queue', sa.Column('response_xml', sa.Text, nullable=True, comment='QBXML response from Desktop'))
    op.add_column('qb_sync_queue', sa.Column('qbwc_fetched_at', sa.DateTime(timezone=True), nullable=True, comment='When QBWC fetched this request'))


def downgrade() -> None:
    # Remove qb_sync_queue columns
    op.drop_column('qb_sync_queue', 'qbwc_fetched_at')
    op.drop_column('qb_sync_queue', 'response_xml')
    op.drop_column('qb_sync_queue', 'request_xml')

    # Remove index
    op.drop_index('ix_qbconn_qbwc_username', 'qb_connections')

    # Revert OAuth fields to NOT NULL (will fail if Desktop connections exist)
    op.alter_column('qb_connections', 'realm_id', nullable=False)
    op.alter_column('qb_connections', 'access_token_encrypted', nullable=False)
    op.alter_column('qb_connections', 'refresh_token_encrypted', nullable=False)
    op.alter_column('qb_connections', 'access_token_expires_at', nullable=False)
    op.alter_column('qb_connections', 'refresh_token_expires_at', nullable=False)

    # Remove qb_connections columns
    op.drop_column('qb_connections', 'last_qbwc_poll_at')
    op.drop_column('qb_connections', 'company_file_path')
    op.drop_column('qb_connections', 'qb_desktop_version')
    op.drop_column('qb_connections', 'qbwc_password_encrypted')
    op.drop_column('qb_connections', 'qbwc_username')
    op.drop_column('qb_connections', 'connection_type')

    # Drop enum type
    sa.Enum(name='qb_connection_type').drop(op.get_bind(), checkfirst=True)
