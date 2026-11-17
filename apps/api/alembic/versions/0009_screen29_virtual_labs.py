"""0009_screen29_virtual_labs

Screen 29 Virtual Labs: lab_sessions, lab_approvals, usage_ledger; entitlement
and metering columns on virtual_labs.

Revision ID: 0009_screen29_virtual_labs
Revises: 0008_screen07_live_classroom
Create Date: 2026-11-17 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0009_screen29_virtual_labs"
down_revision: Union[str, None] = "0008_screen07_live_classroom"
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


LAB_COLUMNS = [
    ("min_semester", sa.Integer(), "2"),
    ("allowed_tracks", sa.JSON(), None),
    ("session_minutes", sa.Integer(), "120"),
    ("meter", sa.String(length=16), "lab_minutes"),
    ("icon", sa.String(length=16), "terminal"),
    ("image", sa.String(length=128), None),
    ("network", sa.String(length=32), "none"),
    ("default_file", sa.String(length=255), None),
]


def upgrade() -> None:
    with op.batch_alter_table("virtual_labs") as batch_op:
        for name, type_, default in LAB_COLUMNS:
            if not _has_column("virtual_labs", name):
                batch_op.add_column(sa.Column(name, type_, nullable=True, server_default=default))

    if not _has_table("lab_sessions"):
        op.create_table(
            "lab_sessions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("lab_id", sa.String(length=64), sa.ForeignKey("virtual_labs.id"), nullable=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("provider", sa.String(length=16), nullable=True),
            sa.Column("container_ref", sa.String(length=128), nullable=True),
            sa.Column("workspace_file", sa.String(length=255), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("last_active_at", sa.DateTime(), nullable=False),
            sa.Column("stopped_at", sa.DateTime(), nullable=True),
            sa.Column("stop_reason", sa.String(length=32), nullable=True),
            *_tenant_columns(),
        )
        for col in ["college_id", "lab_id", "student_id", "status"]:
            op.create_index(f"ix_lab_sessions_{col}", "lab_sessions", [col])

    if not _has_table("lab_approvals"):
        op.create_table(
            "lab_approvals",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("lab_id", sa.String(length=64), sa.ForeignKey("virtual_labs.id"), nullable=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
            sa.Column("aup_accepted_at", sa.DateTime(), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("decided_by", sa.String(length=64), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            *_tenant_columns(),
        )
        for col in ["college_id", "lab_id", "student_id", "status"]:
            op.create_index(f"ix_lab_approvals_{col}", "lab_approvals", [col])

    if not _has_table("usage_ledger"):
        op.create_table(
            "usage_ledger",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("kind", sa.String(length=32), nullable=True),
            sa.Column("amount", sa.Float(), nullable=True),
            sa.Column("period", sa.String(length=7), nullable=True),
            sa.Column("ref_type", sa.String(length=32), nullable=True),
            sa.Column("ref_id", sa.String(length=64), nullable=True),
            *_tenant_columns(),
        )
        for col in ["college_id", "student_id", "kind", "period"]:
            op.create_index(f"ix_usage_ledger_{col}", "usage_ledger", [col])


def downgrade() -> None:
    for table in ["usage_ledger", "lab_approvals", "lab_sessions"]:
        if _has_table(table):
            op.drop_table(table)
    with op.batch_alter_table("virtual_labs") as batch_op:
        for name, _, _ in reversed(LAB_COLUMNS):
            batch_op.drop_column(name)
