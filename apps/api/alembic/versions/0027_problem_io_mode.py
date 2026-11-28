"""Coding problems: io_mode (function = LeetCode-style method run by the judge's driver; stdio = a program
that reads input and prints output, any language).

Revision ID: 0027_problem_io_mode
Revises: 0026_livekit
Create Date: 2026-11-27 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0027_problem_io_mode'
down_revision: Union[str, None] = '0026_livekit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('coding_problems', schema=None) as batch_op:
        batch_op.add_column(sa.Column('io_mode', sa.String(length=16), nullable=False, server_default='stdio'))
    # existing LeetCode-style problems (a class with methods to fill in) are judged through the driver
    op.execute("UPDATE coding_problems SET io_mode = 'function' WHERE starter_code LIKE '%class Solution%' "
               "OR starter_code LIKE '%class MinStack%'")


def downgrade() -> None:
    with op.batch_alter_table('coding_problems', schema=None) as batch_op:
        batch_op.drop_column('io_mode')
