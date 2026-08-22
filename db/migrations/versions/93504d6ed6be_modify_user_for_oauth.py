"""modify_user_for_oauth

Revision ID: 93504d6ed6be
Revises: fe129e980b68
Create Date: 2026-07-05 19:57:54.835505

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "93504d6ed6be"
down_revision: Union[str, Sequence[str], None] = "fe129e980b68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("organization", sa.Text(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False),
        sa.Column("google_id", sa.String(), nullable=True),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("google_access_token", sa.String(), nullable=True),
        sa.Column("google_refresh_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user")
