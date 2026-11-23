"""One account per email: repair duplicates, then a unique index on users.email.

A cohort student and a trainer had been seeded with the same address, which made
sign-in fail for both (found by the lab launch storm). Later duplicates of an email
(by created_at, then id) get a numeric suffix before the "@"; the first keeps it.

Revision ID: 0018_unique_email
Revises: 0017_certificates
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0018_unique_email'
down_revision: Union[str, None] = '0017_certificates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dupes = conn.execute(sa.text("SELECT email FROM users GROUP BY email HAVING COUNT(*) > 1")).scalars().all()
    taken = set(conn.execute(sa.text("SELECT email FROM users")).scalars().all())
    for email in dupes:
        rows = conn.execute(sa.text("SELECT id FROM users WHERE email = :e ORDER BY created_at, id"), {"e": email}).scalars().all()
        local, _, domain = email.partition("@")
        n = 1
        for uid in rows[1:]:
            new = email
            while new in taken:
                n += 1
                new = f"{local}{n}@{domain}"
            taken.add(new)
            conn.execute(sa.text("UPDATE users SET email = :n WHERE id = :i"), {"n": new, "i": uid})
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=False)
