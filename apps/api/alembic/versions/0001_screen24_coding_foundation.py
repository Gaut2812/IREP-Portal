"""0001_screen24_coding_foundation

Revision ID: 0001_coding_foundation
Revises: 
Create Date: 2026-11-12 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_coding_foundation"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create test_cases table if it doesn't exist
    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("college_id", sa.String(length=64), nullable=False),
        sa.Column("problem_id", sa.String(length=64), nullable=False),
        sa.Column("test_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("input_data", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["problem_id"],
            ["coding_problems.id"],
            name="fk_test_cases_problem_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("test_cases", schema=None) as batch_op:
        batch_op.create_index("ix_test_cases_college_id", ["college_id"], unique=False)
        batch_op.create_index("ix_test_cases_problem_id", ["problem_id"], unique=False)
        batch_op.create_index("ix_test_cases_is_hidden", ["is_hidden"], unique=False)
        batch_op.create_index("ix_test_cases_problem_order", ["problem_id", "test_order"], unique=False)

    # 2. Add Screen 24 columns to coding_problems if missing
    with op.batch_alter_table("coding_problems", schema=None) as batch_op:
        # Check and add columns safely using batch operations
        try:
            batch_op.add_column(sa.Column("slug", sa.String(length=128), nullable=True))
            batch_op.create_index("ix_coding_problems_slug", ["slug"], unique=False)
        except Exception:
            pass
        try:
            batch_op.add_column(sa.Column("time_limit_ms", sa.Integer(), nullable=False, server_default="2000"))
        except Exception:
            pass
        try:
            batch_op.add_column(sa.Column("memory_limit_mb", sa.Integer(), nullable=False, server_default="256"))
        except Exception:
            pass
        try:
            batch_op.add_column(sa.Column("starter_codes", sa.JSON(), nullable=True))
        except Exception:
            pass

    # 3. Add error_message to coding_submissions if missing
    with op.batch_alter_table("coding_submissions", schema=None) as batch_op:
        try:
            batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        except Exception:
            pass

    # 4. Create submission_results table
    op.create_table(
        "submission_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("college_id", sa.String(length=64), nullable=False),
        sa.Column("submission_id", sa.String(length=64), nullable=False),
        sa.Column("test_case_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("runtime_ms", sa.Integer(), nullable=True),
        sa.Column("memory_mb", sa.Float(), nullable=True),
        sa.Column("actual_output", sa.Text(), nullable=True),
        sa.Column("error_output", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["coding_submissions.id"],
            name="fk_submission_results_submission_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["test_case_id"],
            ["test_cases.id"],
            name="fk_submission_results_test_case_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("submission_results", schema=None) as batch_op:
        batch_op.create_index("ix_submission_results_college_id", ["college_id"], unique=False)
        batch_op.create_index("ix_submission_results_submission_id", ["submission_id"], unique=False)
        batch_op.create_index("ix_submission_results_test_case_id", ["test_case_id"], unique=False)
        batch_op.create_index("ix_submission_results_status", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("submission_results")
    op.drop_table("test_cases")
    with op.batch_alter_table("coding_problems", schema=None) as batch_op:
        batch_op.drop_column("starter_codes")
        batch_op.drop_column("memory_limit_mb")
        batch_op.drop_column("time_limit_ms")
        batch_op.drop_column("slug")
    with op.batch_alter_table("coding_submissions", schema=None) as batch_op:
        batch_op.drop_column("error_message")

