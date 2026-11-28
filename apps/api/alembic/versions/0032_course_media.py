"""Library courses: a description, a thumbnail and an intro video per course, and a video per lesson (storage keys).

Revision ID: 0032_course_media
Revises: 0031_message_edit_delete
Create Date: 2026-11-28 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0032_course_media'
down_revision: Union[str, None] = '0031_message_edit_delete'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description_en', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('description_ta', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('thumbnail_key', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('intro_video_key', sa.String(length=255), nullable=True))
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.add_column(sa.Column('video_key', sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.drop_column('video_key')
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('intro_video_key')
        batch_op.drop_column('thumbnail_key')
        batch_op.drop_column('description_ta')
        batch_op.drop_column('description_en')
