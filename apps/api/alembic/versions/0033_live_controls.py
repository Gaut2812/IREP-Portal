"""Live classroom controls: in-class chat (with pins), raised hands, reactions, and a spotlight on the meeting.

Revision ID: 0033_live_controls
Revises: 0032_course_media
Create Date: 2026-11-28 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0033_live_controls'
down_revision: Union[str, None] = '0032_course_media'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _common():
    return [sa.Column('college_id', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        'live_chat_messages',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('author_name', sa.String(length=128), nullable=False),
        sa.Column('author_role', sa.String(length=16), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
        *_common(),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name='fk_live_chat_session'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_live_chat_messages_session_id', 'live_chat_messages', ['session_id'])
    op.create_index('ix_live_chat_messages_college_id', 'live_chat_messages', ['college_id'])
    op.create_table(
        'live_hands',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('raised_at', sa.DateTime(), nullable=False),
        *_common(),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name='fk_live_hand_session'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'user_id', name='uq_live_hand'),
    )
    op.create_index('ix_live_hands_session_id', 'live_hands', ['session_id'])
    op.create_index('ix_live_hands_college_id', 'live_hands', ['college_id'])
    op.create_table(
        'live_reactions',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=64), nullable=False),
        sa.Column('emoji', sa.String(length=8), nullable=False),
        *_common(),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], name='fk_live_reaction_session'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_live_reactions_session_id', 'live_reactions', ['session_id'])
    op.create_index('ix_live_reactions_college_id', 'live_reactions', ['college_id'])
    with op.batch_alter_table('live_meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('spotlight_user_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('live_meetings', schema=None) as batch_op:
        batch_op.drop_column('spotlight_user_id')
    for t in ('live_reactions', 'live_hands', 'live_chat_messages'):
        op.drop_table(t)
