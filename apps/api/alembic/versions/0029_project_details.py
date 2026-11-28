"""Sprint board: project description and goals on the team, and who created each task (students edit their tasks).

Revision ID: 0029_project_details
Revises: 0028_attempt_pause
Create Date: 2026-11-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0029_project_details'
down_revision: Union[str, None] = '0028_attempt_pause'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('goals', sa.Text(), nullable=True))
    with op.batch_alter_table('sprint_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_student_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('sprint_tasks', schema=None) as batch_op:
        batch_op.drop_column('created_by_student_id')
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.drop_column('goals')
        batch_op.drop_column('description')
