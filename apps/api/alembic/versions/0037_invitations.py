"""Invitations: who was invited, by whom, and whether they accepted. Local mode carries a one-time set-password token
(stored as a SHA-256 hash, 48 hours); Keycloak mode keeps Keycloak's own email link.

Revision ID: 0037_invitations
Revises: 0036_dm_edit_delete
Create Date: 2026-11-28 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0037_invitations'
down_revision: Union[str, None] = '0036_dm_edit_delete'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'invitations',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=16), nullable=False, server_default='local'),
        sa.Column('token_hash', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('send_seq', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('emailed_seq', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_sent_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('invited_by', sa.String(length=64), nullable=True),
        sa.Column('invited_by_name', sa.String(length=128), nullable=True),
        sa.Column('college_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_invitations_user_id_users'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_invitations_college_id', 'invitations', ['college_id'])
    op.create_index('ix_invitations_user_id', 'invitations', ['user_id'], unique=True)
    op.create_index('ix_invitations_token_hash', 'invitations', ['token_hash'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_invitations_token_hash', table_name='invitations')
    op.drop_index('ix_invitations_user_id', table_name='invitations')
    op.drop_index('ix_invitations_college_id', table_name='invitations')
    op.drop_table('invitations')
