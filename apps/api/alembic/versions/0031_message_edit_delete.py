"""Discussion messages: edited and deleted by the sender (the original text is kept for moderators).

Revision ID: 0031_message_edit_delete
Revises: 0030_buddy_conversations
Create Date: 2026-11-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0031_message_edit_delete'
down_revision: Union[str, None] = '0030_buddy_conversations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('group_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('edited_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('deleted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('original_text', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('group_messages', schema=None) as batch_op:
        batch_op.drop_column('original_text')
        batch_op.drop_column('deleted_at')
        batch_op.drop_column('edited_at')
