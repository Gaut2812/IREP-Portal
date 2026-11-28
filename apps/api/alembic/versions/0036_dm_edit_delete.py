"""Thread messages (trainer, parent, college): the sender may edit within 15 minutes or delete for everyone;
the first text is kept for audit.

Revision ID: 0036_dm_edit_delete
Revises: 0035_rsvp_deadline
Create Date: 2026-11-28 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0036_dm_edit_delete'
down_revision: Union[str, None] = '0035_rsvp_deadline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('direct_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('edited_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('first_text', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('direct_messages', schema=None) as batch_op:
        batch_op.drop_column('first_text')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('edited_at')
