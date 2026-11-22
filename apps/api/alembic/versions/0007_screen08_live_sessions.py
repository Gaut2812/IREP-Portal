"""0007_screen08_live_sessions

Screen 08 Live Sessions & Recordings: recordings, reminders, recording_views.

Revision ID: 0007_screen08_live_sessions
Revises: 0006_screen15_parent_view
Create Date: 2026-11-17 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007_screen08_live_sessions"
down_revision: Union[str, None] = "0006_screen15_parent_view"
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
    if not _has_table("recordings"):
        op.create_table(
            "recordings",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("session_id", sa.String(length=64), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("batch_id", sa.String(length=64), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("storage_key", sa.String(length=512), nullable=False),
            sa.Column("duration_min", sa.Integer(), nullable=True),
            sa.Column("chapters", sa.JSON(), nullable=True),
            sa.Column("has_transcript", sa.Boolean(), nullable=True),
            sa.Column("has_summary", sa.Boolean(), nullable=True),
            sa.Column("recorded_on", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            *_tenant_columns(),
        )
        for col in ["college_id", "session_id", "batch_id"]:
            op.create_index(f"ix_recordings_{col}", "recordings", [col])

    if not _has_table("reminders"):
        op.create_table(
            "reminders",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("session_id", sa.String(length=64), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("channel", sa.String(length=16), nullable=True),
            sa.Column("remind_at", sa.DateTime(), nullable=True),
            sa.Column("delivered", sa.Boolean(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("user_id", "session_id", name="uq_reminder_user_session"),
        )
        for col in ["college_id", "user_id", "session_id"]:
            op.create_index(f"ix_reminders_{col}", "reminders", [col])

    if not _has_table("recording_views"):
        op.create_table(
            "recording_views",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("recording_id", sa.String(length=64), sa.ForeignKey("recordings.id"), nullable=True),
            sa.Column("watched_seconds", sa.Integer(), nullable=True),
            sa.Column("completed", sa.Boolean(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("student_id", "recording_id", name="uq_recording_view"),
        )
        for col in ["college_id", "student_id", "recording_id"]:
            op.create_index(f"ix_recording_views_{col}", "recording_views", [col])


def downgrade() -> None:
    for table in ["recording_views", "reminders", "recordings"]:
        if _has_table(table):
            op.drop_table(table)
