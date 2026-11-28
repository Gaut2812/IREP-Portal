"""Study Buddy: saved conversations (title, course context, mode) and thumbs feedback on answers.

Revision ID: 0030_buddy_conversations
Revises: 0029_project_details
Create Date: 2026-11-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0030_buddy_conversations'
down_revision: Union[str, None] = '0029_project_details'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'buddy_conversations',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('student_id', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('course_id', sa.String(length=64), nullable=True),
        sa.Column('mode', sa.String(length=16), nullable=False, server_default='tutor'),
        sa.Column('college_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name='fk_buddy_conv_student'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('buddy_conversations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_buddy_conversations_student_id'), ['student_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_buddy_conversations_college_id'), ['college_id'], unique=False)

    with op.batch_alter_table('study_buddy_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('conversation_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('feedback', sa.String(length=8), nullable=True))
        batch_op.create_index(batch_op.f('ix_study_buddy_messages_conversation_id'), ['conversation_id'], unique=False)
        batch_op.create_foreign_key('fk_buddy_msg_conversation', 'buddy_conversations', ['conversation_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('study_buddy_messages', schema=None) as batch_op:
        batch_op.drop_constraint('fk_buddy_msg_conversation', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_study_buddy_messages_conversation_id'))
        batch_op.drop_column('feedback')
        batch_op.drop_column('conversation_id')
    with op.batch_alter_table('buddy_conversations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_buddy_conversations_college_id'))
        batch_op.drop_index(batch_op.f('ix_buddy_conversations_student_id'))
    op.drop_table('buddy_conversations')
