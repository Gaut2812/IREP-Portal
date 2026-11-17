"""0008_screen07_live_classroom

Screen 07 Live Classroom: live_meetings, join_events, live_polls,
live_poll_votes, qa_questions, qa_upvotes; attendance source/override columns.

Revision ID: 0008_screen07_live_classroom
Revises: 0007_screen08_live_sessions
Create Date: 2026-11-17 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0008_screen07_live_classroom"
down_revision: Union[str, None] = "0007_screen08_live_sessions"
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


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_table("live_meetings"):
        op.create_table(
            "live_meetings",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("session_id", sa.String(length=64), sa.ForeignKey("sessions.id"), nullable=True, unique=True),
            sa.Column("provider", sa.String(length=16), nullable=True),
            sa.Column("external_meeting_id", sa.String(length=128), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("is_recording", sa.Boolean(), nullable=True),
            sa.Column("sharing_user_name", sa.String(length=128), nullable=True),
            sa.Column("shared_file", sa.String(length=255), nullable=True),
            sa.Column("shared_source", sa.String(length=128), nullable=True),
            sa.Column("shared_code", sa.Text(), nullable=True),
            sa.Column("flow_title", sa.String(length=128), nullable=True),
            sa.Column("flow_steps", sa.JSON(), nullable=True),
            sa.Column("finalized", sa.Boolean(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_live_meetings_college_id", "live_meetings", ["college_id"])

    if not _has_table("join_events"):
        op.create_table(
            "join_events",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("session_id", sa.String(length=64), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("event", sa.String(length=16), nullable=False),
            sa.Column("at", sa.DateTime(), nullable=False),
            sa.Column("source", sa.String(length=16), nullable=True),
            *_tenant_columns(),
        )
        for col in ["college_id", "session_id", "user_id", "at"]:
            op.create_index(f"ix_join_events_{col}", "join_events", [col])

    if not _has_table("live_polls"):
        op.create_table(
            "live_polls",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("session_id", sa.String(length=64), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("options", sa.JSON(), nullable=True),
            sa.Column("is_open", sa.Boolean(), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_live_polls_session_id", "live_polls", ["session_id"])

    if not _has_table("live_poll_votes"):
        op.create_table(
            "live_poll_votes",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("poll_id", sa.String(length=64), sa.ForeignKey("live_polls.id"), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("option_key", sa.String(length=8), nullable=False),
            *_tenant_columns(),
            sa.UniqueConstraint("poll_id", "user_id", name="uq_poll_vote_user"),
        )
        op.create_index("ix_live_poll_votes_poll_id", "live_poll_votes", ["poll_id"])

    if not _has_table("qa_questions"):
        op.create_table(
            "qa_questions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("session_id", sa.String(length=64), sa.ForeignKey("sessions.id"), nullable=True),
            sa.Column("author_user_id", sa.String(length=64), nullable=True),
            sa.Column("author_name", sa.String(length=128), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("answered_at_sec", sa.Integer(), nullable=True),
            sa.Column("is_hidden", sa.Boolean(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_qa_questions_session_id", "qa_questions", ["session_id"])

    if not _has_table("qa_upvotes"):
        op.create_table(
            "qa_upvotes",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("question_id", sa.String(length=64), sa.ForeignKey("qa_questions.id"), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("question_id", "user_id", name="uq_qa_upvote_user"),
        )
        op.create_index("ix_qa_upvotes_question_id", "qa_upvotes", ["question_id"])

    with op.batch_alter_table("session_attendance") as batch_op:
        if not _has_column("session_attendance", "source"):
            batch_op.add_column(sa.Column("source", sa.String(length=16), nullable=True, server_default="auto"))
        if not _has_column("session_attendance", "overridden_by"):
            batch_op.add_column(sa.Column("overridden_by", sa.String(length=64), nullable=True))
        if not _has_column("session_attendance", "override_reason"):
            batch_op.add_column(sa.Column("override_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("session_attendance") as batch_op:
        batch_op.drop_column("override_reason")
        batch_op.drop_column("overridden_by")
        batch_op.drop_column("source")
    for table in ["qa_upvotes", "qa_questions", "live_poll_votes", "live_polls", "join_events", "live_meetings"]:
        if _has_table(table):
            op.drop_table(table)
