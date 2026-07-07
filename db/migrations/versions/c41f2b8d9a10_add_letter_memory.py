"""add_letter_memory

Revision ID: c41f2b8d9a10
Revises: 93504d6ed6be
Create Date: 2026-07-07

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "c41f2b8d9a10"
down_revision: Union[str, Sequence[str], None] = "93504d6ed6be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "letter_memory",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_doc_id", sa.String(), nullable=True, unique=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # ponytail: no vector index; sequential scan is fine below a few thousand
    # letters. Add an HNSW index if retrieval ever gets slow.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("letter_memory")
