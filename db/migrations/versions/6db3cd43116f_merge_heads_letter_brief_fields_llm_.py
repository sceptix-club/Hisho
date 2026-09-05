"""merge heads: letter brief fields + llm extraction overhaul

Revision ID: 6db3cd43116f
Revises: 200be0292be9, db91529bd874
Create Date: 2026-09-05 22:07:14.595199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6db3cd43116f'
down_revision: Union[str, Sequence[str], None] = ('200be0292be9', 'db91529bd874')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
