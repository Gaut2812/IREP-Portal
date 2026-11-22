"""0004_screen13_trainer_dashboard

Screen 13 Trainer Dashboard / 14 At-Risk: rules_config, at_risk_flags, flag_actions.

Revision ID: 0004_screen13_trainer_dashboard
Revises: 0003_screen12_dashboard
Create Date: 2026-11-16 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0004_screen13_trainer_dashboard"
down_revision: Union[str, None] = "0003_screen12_dashboard"
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
    if not _has_table("rules_config"):
        op.create_table(
            "rules_config",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("score_below", sa.Integer(), nullable=True),
            sa.Column("attendance_below", sa.Integer(), nullable=True),
            sa.Column("missed_sessions", sa.Integer(), nullable=True),
            sa.Column("project_delay_days", sa.Integer(), nullable=True),
            sa.Column("quiet_hours_start", sa.Integer(), nullable=True),
            sa.Column("quiet_hours_end", sa.Integer(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_rules_config_college_id", "rules_config", ["college_id"])

    if not _has_table("at_risk_flags"):
        op.create_table(
            "at_risk_flags",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("batch_id", sa.String(length=64), nullable=True),
            sa.Column("reason_key", sa.String(length=32), nullable=False),
            sa.Column("reason_text", sa.String(length=255), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=True),
            sa.Column("suggested_action", sa.String(length=32), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("parent_notified", sa.Boolean(), nullable=True),
            sa.Column("parent_notified_at", sa.DateTime(), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("resolved_by", sa.String(length=64), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("flagged_on", sa.Date(), nullable=True),
            *_tenant_columns(),
        )
        for col in ["college_id", "student_id", "batch_id", "reason_key", "status"]:
            op.create_index(f"ix_at_risk_flags_{col}", "at_risk_flags", [col])

    if not _has_table("flag_actions"):
        op.create_table(
            "flag_actions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("flag_id", sa.String(length=64), sa.ForeignKey("at_risk_flags.id"), nullable=True),
            sa.Column("action_type", sa.String(length=32), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("actor_user_id", sa.String(length=64), nullable=True),
            sa.Column("actor_name", sa.String(length=128), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_flag_actions_college_id", "flag_actions", ["college_id"])
        op.create_index("ix_flag_actions_flag_id", "flag_actions", ["flag_id"])


def downgrade() -> None:
    for table in ["flag_actions", "at_risk_flags", "rules_config"]:
        if _has_table(table):
            op.drop_table(table)
