"""0003_screen12_dashboard

Screen 12 Student Dashboard: readiness_config, skill_scores,
readiness_snapshots, badges, student_badges, events.

Revision ID: 0003_screen12_dashboard
Revises: 0002_foundation_cohort
Create Date: 2026-11-16 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_screen12_dashboard"
down_revision: Union[str, None] = "0002_foundation_cohort"
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
    if not _has_table("readiness_config"):
        op.create_table(
            "readiness_config",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("weights", sa.JSON(), nullable=True),
            sa.Column("band_ready_min", sa.Integer(), nullable=True),
            sa.Column("band_nearly_min", sa.Integer(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_readiness_config_college_id", "readiness_config", ["college_id"])

    if not _has_table("skill_scores"):
        op.create_table(
            "skill_scores",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("skill_key", sa.String(length=32), nullable=False),
            sa.Column("label_en", sa.String(length=128), nullable=False),
            sa.Column("label_ta", sa.String(length=128), nullable=True),
            sa.Column("percentage", sa.Integer(), nullable=True),
            sa.Column("color", sa.String(length=16), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("student_id", "skill_key", name="uq_skill_score_student_skill"),
        )
        op.create_index("ix_skill_scores_college_id", "skill_scores", ["college_id"])
        op.create_index("ix_skill_scores_student_id", "skill_scores", ["student_id"])

    if not _has_table("readiness_snapshots"):
        op.create_table(
            "readiness_snapshots",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("snapshot_date", sa.Date(), nullable=True),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("band", sa.String(length=32), nullable=True),
            sa.Column("delta", sa.Integer(), nullable=True),
            sa.Column("breakdown", sa.JSON(), nullable=True),
            sa.Column("config_version", sa.Integer(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_readiness_snapshots_college_id", "readiness_snapshots", ["college_id"])
        op.create_index("ix_readiness_snapshots_student_id", "readiness_snapshots", ["student_id"])
        op.create_index("ix_readiness_snapshots_snapshot_date", "readiness_snapshots", ["snapshot_date"])

    if not _has_table("badges"):
        op.create_table(
            "badges",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name_en", sa.String(length=128), nullable=False),
            sa.Column("name_ta", sa.String(length=128), nullable=True),
            sa.Column("description_en", sa.String(length=255), nullable=False),
            sa.Column("description_ta", sa.String(length=255), nullable=True),
            sa.Column("icon", sa.String(length=16), nullable=True),
            sa.Column("rule", sa.String(length=255), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_badges_college_id", "badges", ["college_id"])

    if not _has_table("student_badges"):
        op.create_table(
            "student_badges",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("badge_id", sa.String(length=64), sa.ForeignKey("badges.id"), nullable=True),
            sa.Column("earned_on", sa.Date(), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("student_id", "badge_id", name="uq_student_badge"),
        )
        op.create_index("ix_student_badges_college_id", "student_badges", ["college_id"])
        op.create_index("ix_student_badges_student_id", "student_badges", ["student_id"])

    if not _has_table("events"):
        op.create_table(
            "events",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("title_en", sa.String(length=255), nullable=False),
            sa.Column("title_ta", sa.String(length=255), nullable=True),
            sa.Column("kind", sa.String(length=32), nullable=True),
            sa.Column("starts_at", sa.DateTime(), nullable=True),
            sa.Column("ends_at", sa.DateTime(), nullable=True),
            sa.Column("audience", sa.String(length=32), nullable=True),
            sa.Column("batch_id", sa.String(length=64), nullable=True),
            sa.Column("student_id", sa.String(length=64), nullable=True),
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("description_en", sa.Text(), nullable=True),
            sa.Column("description_ta", sa.Text(), nullable=True),
            sa.Column("rsvp_enabled", sa.Boolean(), nullable=True),
            sa.Column("created_by", sa.String(length=64), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_events_college_id", "events", ["college_id"])
        op.create_index("ix_events_kind", "events", ["kind"])
        op.create_index("ix_events_starts_at", "events", ["starts_at"])
        op.create_index("ix_events_batch_id", "events", ["batch_id"])
        op.create_index("ix_events_student_id", "events", ["student_id"])


def downgrade() -> None:
    for table in ["events", "student_badges", "badges", "readiness_snapshots", "skill_scores", "readiness_config"]:
        if _has_table(table):
            op.drop_table(table)
