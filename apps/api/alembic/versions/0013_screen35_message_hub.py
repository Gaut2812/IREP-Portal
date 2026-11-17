"""0013_screen35_message_hub

Screen 35 Trainer Message Hub: direct-message read/sender/language columns,
translations_cache and broadcasts.

Revision ID: 0013_screen35_message_hub
Revises: 0012_screen34_discussions
Create Date: 2026-11-17 23:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0013_screen35_message_hub"
down_revision: Union[str, None] = "0012_screen34_discussions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DM_COLUMNS = [("sender_user_id", sa.String(length=64), None), ("original_lang", sa.String(length=8), "en"), ("read_at", sa.DateTime(), None)]


def _tenant_columns():
    return [
        sa.Column("college_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    existing = {c["name"] for c in _inspector().get_columns("direct_messages")}
    with op.batch_alter_table("direct_messages") as batch_op:
        for name, type_, default in DM_COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, type_, nullable=True, server_default=default))
    if not _inspector().has_table("translations_cache"):
        op.create_table(
            "translations_cache",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("src", sa.String(length=8), nullable=False),
            sa.Column("dst", sa.String(length=8), nullable=False),
            sa.Column("source_text", sa.Text(), nullable=False),
            sa.Column("translated_text", sa.Text(), nullable=False),
            sa.Column("engine", sa.String(length=32), nullable=True),
            *_tenant_columns(),
        )
    if not _inspector().has_table("broadcasts"):
        op.create_table(
            "broadcasts",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("author_user_id", sa.String(length=64), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("audience", sa.String(length=16), nullable=False),
            sa.Column("batch_ids", sa.Text(), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("delivery", sa.Text(), nullable=True),
            *_tenant_columns(),
        )


def downgrade() -> None:
    for table in ["broadcasts", "translations_cache"]:
        if _inspector().has_table(table):
            op.drop_table(table)
    with op.batch_alter_table("direct_messages") as batch_op:
        for name, _, _ in DM_COLUMNS:
            batch_op.drop_column(name)
