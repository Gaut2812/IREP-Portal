"""RSVP: a reply deadline the college may set per event, and an optional reason when a parent says not attending.

Revision ID: 0035_rsvp_deadline
Revises: 0034_flag_mentor
Create Date: 2026-11-28 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0035_rsvp_deadline'
down_revision: Union[str, None] = '0034_flag_mentor'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rsvp_deadline', sa.DateTime(), nullable=True))
    with op.batch_alter_table('rsvps', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reason', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('rsvps', schema=None) as batch_op:
        batch_op.drop_column('reason')
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_column('rsvp_deadline')
