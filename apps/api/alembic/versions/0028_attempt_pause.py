"""Practice test attempts: last heartbeat and paused seconds, so a lost connection pauses the clock (capped).

Revision ID: 0028_attempt_pause
Revises: 0027_problem_io_mode
Create Date: 2026-11-27 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0028_attempt_pause'
down_revision: Union[str, None] = '0027_problem_io_mode'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('test_attempts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_seen_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('paused_seconds', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('test_attempts', schema=None) as batch_op:
        batch_op.drop_column('paused_seconds')
        batch_op.drop_column('last_seen_at')
