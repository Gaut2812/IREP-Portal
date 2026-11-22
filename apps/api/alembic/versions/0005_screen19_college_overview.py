"""0005_screen19_college_overview

Screen 19 College Dashboard: report_runs.

Revision ID: 0005_screen19_college_overview
Revises: 0004_screen13_trainer_dashboard
Create Date: 2026-11-17 09:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005_screen19_college_overview"
down_revision: Union[str, None] = "0004_screen13_trainer_dashboard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("report_runs"):
        op.create_table(
            "report_runs",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("title_en", sa.String(length=255), nullable=False),
            sa.Column("title_ta", sa.String(length=255), nullable=True),
            sa.Column("report_type", sa.String(length=32), nullable=True),
            sa.Column("period_label", sa.String(length=64), nullable=True),
            sa.Column("generated_at", sa.DateTime(), nullable=True),
            sa.Column("data_as_of", sa.Date(), nullable=True),
            sa.Column("file_path", sa.String(length=512), nullable=True),
            sa.Column("file_size_kb", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=True),
            sa.Column("generated_by", sa.String(length=64), nullable=True),
            sa.Column("college_id", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_report_runs_college_id", "report_runs", ["college_id"])


def downgrade() -> None:
    if _has_table("report_runs"):
        op.drop_table("report_runs")
