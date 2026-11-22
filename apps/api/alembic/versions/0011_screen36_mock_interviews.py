"""0011_screen36_mock_interviews

Screen 36 Mock Interviews: rubric_config, interview_slots, interview_bookings
(UNIQUE slot_id = no double booking), interviews, rubric_scores, interview_comments.

Revision ID: 0011_screen36_mock_interviews
Revises: 0010_screen30_sprint_board
Create Date: 2026-11-17 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0011_screen36_mock_interviews"
down_revision: Union[str, None] = "0010_screen30_sprint_board"
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
    if not _has_table("rubric_config"):
        op.create_table(
            "rubric_config",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("round_type", sa.String(length=32), nullable=True),
            sa.Column("criteria", sa.JSON(), nullable=True),
            sa.Column("max_score", sa.Integer(), nullable=True),
            sa.Column("service_ready_min", sa.Float(), nullable=True),
            sa.Column("product_ready_min", sa.Float(), nullable=True),
            *_tenant_columns(),
        )
    if not _has_table("interview_slots"):
        op.create_table(
            "interview_slots",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("trainer_id", sa.String(length=64), sa.ForeignKey("trainers.id"), nullable=True),
            sa.Column("batch_id", sa.String(length=64), nullable=True),
            sa.Column("round_type", sa.String(length=32), nullable=True),
            sa.Column("starts_at", sa.DateTime(), nullable=True),
            sa.Column("duration_min", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_interview_slots_trainer_id", "interview_slots", ["trainer_id"])
        op.create_index("ix_interview_slots_starts_at", "interview_slots", ["starts_at"])
    if not _has_table("interview_bookings"):
        op.create_table(
            "interview_bookings",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("slot_id", sa.String(length=64), sa.ForeignKey("interview_slots.id"), nullable=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("interview_id", sa.String(length=64), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("slot_id", name="uq_booking_slot"),
        )
        op.create_index("ix_interview_bookings_student_id", "interview_bookings", ["student_id"])
    if not _has_table("interviews"):
        op.create_table(
            "interviews",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("trainer_id", sa.String(length=64), sa.ForeignKey("trainers.id"), nullable=True),
            sa.Column("slot_id", sa.String(length=64), nullable=True),
            sa.Column("round_number", sa.Integer(), nullable=True),
            sa.Column("round_type", sa.String(length=32), nullable=True),
            sa.Column("scheduled_at", sa.DateTime(), nullable=True),
            sa.Column("duration_min", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("feedback_en", sa.Text(), nullable=True),
            sa.Column("feedback_ta", sa.Text(), nullable=True),
            sa.Column("recording_key", sa.String(length=512), nullable=True),
            sa.Column("recording_started_at", sa.DateTime(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_interviews_student_id", "interviews", ["student_id"])
        op.create_index("ix_interviews_status", "interviews", ["status"])
    if not _has_table("rubric_scores"):
        op.create_table(
            "rubric_scores",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("interview_id", sa.String(length=64), sa.ForeignKey("interviews.id"), nullable=True),
            sa.Column("criterion_key", sa.String(length=32), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("interview_id", "criterion_key", name="uq_rubric_score"),
        )
    if not _has_table("interview_comments"):
        op.create_table(
            "interview_comments",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("interview_id", sa.String(length=64), sa.ForeignKey("interviews.id"), nullable=True),
            sa.Column("at_seconds", sa.Integer(), nullable=True),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("author_name", sa.String(length=128), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_interview_comments_interview_id", "interview_comments", ["interview_id"])


def downgrade() -> None:
    for table in ["interview_comments", "rubric_scores", "interviews", "interview_bookings", "interview_slots", "rubric_config"]:
        if _has_table(table):
            op.drop_table(table)
