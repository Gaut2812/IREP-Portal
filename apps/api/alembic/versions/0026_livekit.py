"""LiveKit live classroom: webhook dedupe id on join events, screen-share grants on meetings.

Revision ID: 0026_livekit
Revises: 0025_dpdp
Create Date: 2026-11-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0026_livekit'
down_revision: Union[str, None] = '0025_dpdp'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('join_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('external_id', sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint('uq_join_events_external_id', ['external_id'])

    with op.batch_alter_table('live_meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('share_grants', sa.JSON(), nullable=False, server_default=sa.text("'[]'")))  # existing rows


def downgrade() -> None:
    with op.batch_alter_table('live_meetings', schema=None) as batch_op:
        batch_op.drop_column('share_grants')

    with op.batch_alter_table('join_events', schema=None) as batch_op:
        batch_op.drop_constraint('uq_join_events_external_id', type_='unique')
        batch_op.drop_column('external_id')
