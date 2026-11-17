"""0012_screen34_discussions

Screen 34 Discussion Groups: group_members, reactions, reports,
moderation_actions; group/message/thread/college columns.

Revision ID: 0012_screen34_discussions
Revises: 0011_screen36_mock_interviews
Create Date: 2026-11-17 22:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0012_screen34_discussions"
down_revision: Union[str, None] = "0011_screen36_mock_interviews"
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


ADDED = {
    "colleges": [("chat_retention_days", sa.Integer(), "365")],
    "discussion_groups": [("kind", sa.String(length=32), "batch"), ("icon", sa.String(length=16), "users"), ("batch_id", sa.String(length=64), None)],
    "group_messages": [("sender_user_id", sa.String(length=64), None), ("is_removed", sa.Boolean(), "0"), ("removed_reason", sa.Text(), None)],
    "trainer_direct_threads": [("contact_user_id", sa.String(length=64), None), ("student_id", sa.String(length=64), None)],
}


def upgrade() -> None:
    for table, cols in ADDED.items():
        with op.batch_alter_table(table) as batch_op:
            for name, type_, default in cols:
                if not _has_column(table, name):
                    batch_op.add_column(sa.Column(name, type_, nullable=True, server_default=default))

    if not _has_table("group_members"):
        op.create_table(
            "group_members",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("group_id", sa.String(length=64), sa.ForeignKey("discussion_groups.id"), nullable=True),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("role", sa.String(length=16), nullable=True),
            sa.Column("last_read_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.Column("muted_until", sa.DateTime(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("group_id", "user_id", name="uq_group_member"),
        )
        op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
        op.create_index("ix_group_members_user_id", "group_members", ["user_id"])
    if not _has_table("reactions"):
        op.create_table(
            "reactions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("message_id", sa.String(length=64), sa.ForeignKey("group_messages.id"), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=True),
            sa.Column("emoji", sa.String(length=8), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("message_id", "user_id", name="uq_reaction_user"),
        )
    if not _has_table("reports"):
        op.create_table(
            "reports",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("message_id", sa.String(length=64), sa.ForeignKey("group_messages.id"), nullable=True),
            sa.Column("group_id", sa.String(length=64), nullable=True),
            sa.Column("reporter_user_id", sa.String(length=64), nullable=True),
            sa.Column("reason", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("message_id", "reporter_user_id", name="uq_report_once"),
        )
        op.create_index("ix_reports_status", "reports", ["status"])
    if not _has_table("moderation_actions"):
        op.create_table(
            "moderation_actions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("report_id", sa.String(length=64), nullable=True),
            sa.Column("message_id", sa.String(length=64), nullable=True),
            sa.Column("target_user_id", sa.String(length=64), nullable=True),
            sa.Column("action", sa.String(length=16), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("actor_user_id", sa.String(length=64), nullable=False),
            *_tenant_columns(),
        )


def downgrade() -> None:
    for table in ["moderation_actions", "reports", "reactions", "group_members"]:
        if _has_table(table):
            op.drop_table(table)
    for table, cols in ADDED.items():
        with op.batch_alter_table(table) as batch_op:
            for name, _, _ in cols:
                batch_op.drop_column(name)
