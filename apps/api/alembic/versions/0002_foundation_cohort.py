"""0002_foundation_cohort

S0 foundation: college structure (branches, batches, batch_trainers),
cohort facts (certificates, internships), governance (audit_log,
otp_attempts, notifications) and the columns that attach students,
sessions and users to them.

Revision ID: 0002_foundation_cohort
Revises: 0001_coding_foundation
Create Date: 2026-11-16 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002_foundation_cohort"
down_revision: Union[str, None] = "0001_coding_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tenant_columns():
    return [
        sa.Column("college_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    if not _has_table("branches"):
        op.create_table(
            "branches",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("track", sa.String(length=64), nullable=True),
            sa.Column("hod_name", sa.String(length=128), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_branches_college_id", "branches", ["college_id"])

    if not _has_table("batches"):
        op.create_table(
            "batches",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("branch_id", sa.String(length=64), sa.ForeignKey("branches.id"), nullable=True),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("short_name", sa.String(length=32), nullable=False),
            sa.Column("semester", sa.Integer(), nullable=True),
            sa.Column("academic_year", sa.String(length=16), nullable=True),
            sa.Column("track", sa.String(length=64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_batches_college_id", "batches", ["college_id"])
        op.create_index("ix_batches_branch_id", "batches", ["branch_id"])
        op.create_index("ix_batches_semester", "batches", ["semester"])

    if not _has_table("batch_trainers"):
        op.create_table(
            "batch_trainers",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("batch_id", sa.String(length=64), sa.ForeignKey("batches.id"), nullable=True),
            sa.Column("trainer_id", sa.String(length=64), sa.ForeignKey("trainers.id"), nullable=True),
            sa.Column("role", sa.String(length=32), nullable=True),
            *_tenant_columns(),
            sa.UniqueConstraint("batch_id", "trainer_id", name="uq_batch_trainer"),
        )
        op.create_index("ix_batch_trainers_college_id", "batch_trainers", ["college_id"])

    if not _has_table("certificates"):
        op.create_table(
            "certificates",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("issuer", sa.String(length=128), nullable=True),
            sa.Column("cert_type", sa.String(length=32), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=True),
            sa.Column("issued_on", sa.Date(), nullable=True),
            sa.Column("exam_date", sa.Date(), nullable=True),
            sa.Column("verify_code", sa.String(length=64), nullable=True),
            sa.Column("proof_url", sa.String(length=512), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_certificates_college_id", "certificates", ["college_id"])
        op.create_index("ix_certificates_student_id", "certificates", ["student_id"])
        op.create_index("ix_certificates_status", "certificates", ["status"])
        op.create_index("ix_certificates_issued_on", "certificates", ["issued_on"])
        op.create_index("ix_certificates_verify_code", "certificates", ["verify_code"])

    if not _has_table("internships"):
        op.create_table(
            "internships",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("student_id", sa.String(length=64), sa.ForeignKey("students.id"), nullable=True),
            sa.Column("company", sa.String(length=128), nullable=False),
            sa.Column("role_title", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=True),
            sa.Column("semester", sa.Integer(), nullable=True),
            sa.Column("secured_on", sa.Date(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_internships_college_id", "internships", ["college_id"])
        op.create_index("ix_internships_student_id", "internships", ["student_id"])

    if not _has_table("audit_log"):
        op.create_table(
            "audit_log",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("actor_user_id", sa.String(length=64), nullable=True),
            sa.Column("actor_role", sa.String(length=32), nullable=True),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=True),
            sa.Column("entity_id", sa.String(length=64), nullable=True),
            sa.Column("detail", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_audit_log_college_id", "audit_log", ["college_id"])
        op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])
        op.create_index("ix_audit_log_action", "audit_log", ["action"])
        op.create_index("ix_audit_log_entity_id", "audit_log", ["entity_id"])

    if not _has_table("otp_attempts"):
        op.create_table(
            "otp_attempts",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("phone_hash", sa.String(length=128), nullable=False),
            sa.Column("otp_hash", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("verify_attempts", sa.Integer(), nullable=True),
            sa.Column("consumed", sa.Boolean(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_otp_attempts_college_id", "otp_attempts", ["college_id"])
        op.create_index("ix_otp_attempts_phone_hash", "otp_attempts", ["phone_hash"])

    if not _has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("kind", sa.String(length=64), nullable=True),
            sa.Column("title_en", sa.String(length=255), nullable=False),
            sa.Column("title_ta", sa.String(length=255), nullable=True),
            sa.Column("body_en", sa.Text(), nullable=True),
            sa.Column("body_ta", sa.Text(), nullable=True),
            sa.Column("link", sa.String(length=255), nullable=True),
            sa.Column("channel", sa.String(length=32), nullable=True),
            sa.Column("delivery_status", sa.String(length=32), nullable=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            *_tenant_columns(),
        )
        op.create_index("ix_notifications_college_id", "notifications", ["college_id"])
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    # Columns on existing tables
    with op.batch_alter_table("students") as batch_op:
        if not _has_column("students", "branch_id"):
            batch_op.add_column(sa.Column("branch_id", sa.String(length=64), nullable=True))
        if not _has_column("students", "batch_id"):
            batch_op.add_column(sa.Column("batch_id", sa.String(length=64), nullable=True))
        if not _has_column("students", "track"):
            batch_op.add_column(sa.Column("track", sa.String(length=64), nullable=True, server_default="AI & Data Science"))
        if not _has_column("students", "academic_year"):
            batch_op.add_column(sa.Column("academic_year", sa.String(length=16), nullable=True, server_default="2026-27"))

    with op.batch_alter_table("users") as batch_op:
        if not _has_column("users", "failed_logins"):
            batch_op.add_column(sa.Column("failed_logins", sa.Integer(), nullable=True, server_default="0"))
        if not _has_column("users", "locked_until"):
            batch_op.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))

    with op.batch_alter_table("sessions") as batch_op:
        if not _has_column("sessions", "batch_id"):
            batch_op.add_column(sa.Column("batch_id", sa.String(length=64), nullable=True))
        if not _has_column("sessions", "week_no"):
            batch_op.add_column(sa.Column("week_no", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("week_no")
        batch_op.drop_column("batch_id")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("locked_until")
        batch_op.drop_column("failed_logins")
    with op.batch_alter_table("students") as batch_op:
        batch_op.drop_column("academic_year")
        batch_op.drop_column("track")
        batch_op.drop_column("batch_id")
        batch_op.drop_column("branch_id")
    for table in ["notifications", "otp_attempts", "audit_log", "internships", "certificates", "batch_trainers", "batches", "branches"]:
        if _has_table(table):
            op.drop_table(table)
