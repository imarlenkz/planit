"""External system ids on classes and students (Ustaz student import)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05 12:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("classes", "students"):
        with op.batch_alter_table(table) as b:
            b.add_column(sa.Column("external_ref", sa.String(length=64), nullable=True))
            b.create_index(f"ix_{table}_external_ref", ["external_ref"])


def downgrade() -> None:
    for table in ("students", "classes"):
        with op.batch_alter_table(table) as b:
            b.drop_index(f"ix_{table}_external_ref")
            b.drop_column("external_ref")
