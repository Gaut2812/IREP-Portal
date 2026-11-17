"""0006_screen15_parent_view

Screen 15 Parent View: monthly_cards and rsvps.

Revision ID: 0006_screen15_parent_view
Revises: 0005_screen19_college_overview
Create Date: 2026-11-17 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006_screen15_parent_view"
down_revision: Union[str, None] = "0005_screen19_college_overview"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_columns():
    return [
        sa.Column("college_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("monthly_cards"):
        op.create_table(
            "monthly_cards",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("rows", sa.JSON(), nullable=True),
            sa.Column("how_to_help_en", sa.Text(), nullable=True),
            sa.Column("how_to_help_ta", sa.Text(), nullable=True),
            sa.Column("trainer_remark_en", sa.Text(), nullable=True),
            sa.Column("trainer_remark_ta", sa.Text(), nullable=True),
            sa.Column("trainer_name", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("approved_by", sa.String(length=64), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("pdf_path", sa.String(length=512), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("student_id", "year", "month", name="uq_monthly_card_student_month"),
        )
        op.create_index("ix_monthly_cards_college_id", "monthly_cards", ["college_id"])
        op.create_index("ix_monthly_cards_student_id", "monthly_cards", ["student_id"])
        op.create_index("ix_monthly_cards_status", "monthly_cards", ["status"])

    if not _has_table("rsvps"):
        op.create_table(
            "rsvps",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("event_id", sa.String(length=64), sa.ForeignKey("events.id"), nullable=True),
            sa.Column("parent_user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("student_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("guests", sa.Integer(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("event_id", "parent_user_id", name="uq_rsvp_event_parent"),
        )
        op.create_index("ix_rsvps_college_id", "rsvps", ["college_id"])
        op.create_index("ix_rsvps_event_id", "rsvps", ["event_id"])
        op.create_index("ix_rsvps_parent_user_id", "rsvps", ["parent_user_id"])


def downgrade() -> None:
    for table in ["rsvps", "monthly_cards"]:
        if _has_table(table):
            op.drop_table(table)
