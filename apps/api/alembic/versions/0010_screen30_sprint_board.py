"""0010_screen30_sprint_board

Screen 30 Sprint Board: teams, team_members, sprints, change_requests,
standups, build_runs; board columns on sprint_tasks.

Revision ID: 0010_screen30_sprint_board
Revises: 0009_screen29_virtual_labs
Create Date: 2026-11-17 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0010_screen30_sprint_board"
down_revision: Union[str, None] = "0009_screen29_virtual_labs"
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
    if not _has_table("teams"):
        op.create_table(
            "teams",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("project_title", sa.String(length=255), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=True),
            sa.Column("client_name", sa.String(length=128), nullable=True),
            sa.Column("repo_full_name", sa.String(length=255), nullable=True),
            sa.Column("trainer_id", sa.String(length=64), sa.ForeignKey("trainers.id"), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_teams_college_id", "teams", ["college_id"])

    if not _has_table("team_members"):
        op.create_table(
            "team_members",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("team_id", sa.String(length=64), sa.ForeignKey("teams.id"), nullable=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("role", sa.String(length=32), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("team_id", "student_id", name="uq_team_member"),
        )
        op.create_index("ix_team_members_team_id", "team_members", ["team_id"])
        op.create_index("ix_team_members_student_id", "team_members", ["student_id"])

    if not _has_table("sprints"):
        op.create_table(
            "sprints",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("team_id", sa.String(length=64), sa.ForeignKey("teams.id"), nullable=True),
            sa.Column("number", sa.Integer(), nullable=True),
            sa.Column("total_sprints", sa.Integer(), nullable=True),
            sa.Column("ends_week", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("velocity", sa.Integer(), nullable=True),
            sa.Column("goal", sa.Text(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_sprints_team_id", "sprints", ["team_id"])

    if not _has_table("change_requests"):
        op.create_table(
            "change_requests",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("team_id", sa.String(length=64), sa.ForeignKey("teams.id"), nullable=True),
            sa.Column("sprint_id", sa.String(length=64), sa.ForeignKey("sprints.id"), nullable=True),
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("task_id", sa.String(length=64), nullable=True),
            sa.Column("raised_by", sa.String(length=64), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_change_requests_team_id", "change_requests", ["team_id"])

    if not _has_table("standups"):
        op.create_table(
            "standups",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("sprint_id", sa.String(length=64), sa.ForeignKey("sprints.id"), nullable=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("standup_date", sa.Date(), nullable=False),
            sa.Column("yesterday", sa.Text(), nullable=False),
            sa.Column("today", sa.Text(), nullable=False),
            sa.Column("blockers", sa.Text(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("sprint_id", "student_id", "standup_date", name="uq_standup_day"),
        )
        op.create_index("ix_standups_sprint_id", "standups", ["sprint_id"])

    if not _has_table("build_runs"):
        op.create_table(
            "build_runs",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("team_id", sa.String(length=64), sa.ForeignKey("teams.id"), nullable=True),
            sa.Column("run_number", sa.Integer(), nullable=True),
            sa.Column("workflow", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("environment", sa.String(length=32), nullable=True),
            sa.Column("url", sa.String(length=512), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_build_runs_team_id", "build_runs", ["team_id"])

    with op.batch_alter_table("sprint_tasks") as batch_op:
        for name, type_, default in [("team_id", sa.String(length=64), None), ("sprint_id", sa.String(length=64), None),
                                     ("position", sa.Integer(), "0"), ("assignee_student_id", sa.String(length=64), None)]:
            if not _has_column("sprint_tasks", name):
                batch_op.add_column(sa.Column(name, type_, nullable=True, server_default=default))


def downgrade() -> None:
    with op.batch_alter_table("sprint_tasks") as batch_op:
        for name in ["assignee_student_id", "position", "sprint_id", "team_id"]:
            batch_op.drop_column(name)
    for table in ["build_runs", "standups", "change_requests", "sprints", "team_members", "teams"]:
        if _has_table(table):
            op.drop_table(table)
