"""add ai_call_logs

Revision ID: b7d41e6a2f90
Revises: 6db3cd43116f
Create Date: 2026-10-16 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7d41e6a2f90'
down_revision: Union[str, Sequence[str], None] = '6db3cd43116f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ai_call_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('invocation_id', sa.String(), nullable=True),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('agent', sa.String(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('tool_name', sa.String(), nullable=True),
        sa.Column(
            'payload',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_call_logs_created_at', 'ai_call_logs', ['created_at'])
    op.create_index('ix_ai_call_logs_invocation_id', 'ai_call_logs', ['invocation_id'])
    op.create_index('ix_ai_call_logs_session_id', 'ai_call_logs', ['session_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ai_call_logs_session_id', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_invocation_id', table_name='ai_call_logs')
    op.drop_index('ix_ai_call_logs_created_at', table_name='ai_call_logs')
    op.drop_table('ai_call_logs')
