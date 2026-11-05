"""iMARLEN ID single sign-on: users.idp_sub, schools.idp_code

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05 09:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("idp_sub", sa.String(length=64), nullable=True))
        b.create_unique_constraint("uq_users_idp_sub", ["idp_sub"])
    with op.batch_alter_table("schools") as b:
        b.add_column(sa.Column("idp_code", sa.String(length=64), nullable=True))
        b.create_unique_constraint("uq_schools_idp_code", ["idp_code"])


def downgrade() -> None:
    with op.batch_alter_table("schools") as b:
        b.drop_constraint("uq_schools_idp_code", type_="unique")
        b.drop_column("idp_code")
    with op.batch_alter_table("users") as b:
        b.drop_constraint("uq_users_idp_sub", type_="unique")
        b.drop_column("idp_sub")
