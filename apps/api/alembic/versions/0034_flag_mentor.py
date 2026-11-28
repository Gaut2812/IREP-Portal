"""At-risk flags: an assigned mentor (a trainer of the college) and when they were assigned.

Revision ID: 0034_flag_mentor
Revises: 0033_live_controls
Create Date: 2026-11-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0034_flag_mentor'
down_revision: Union[str, None] = '0033_live_controls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('at_risk_flags', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mentor_user_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('mentor_assigned_at', sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f('ix_at_risk_flags_mentor_user_id'), ['mentor_user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('at_risk_flags', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_at_risk_flags_mentor_user_id'))
        batch_op.drop_column('mentor_assigned_at')
        batch_op.drop_column('mentor_user_id')
