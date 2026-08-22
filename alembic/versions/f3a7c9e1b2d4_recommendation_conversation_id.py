"""recommendations: add conversation_id (Phase 14 Compose correlation)

Revision ID: f3a7c9e1b2d4
Revises: 7e9d4180004a
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a7c9e1b2d4'
down_revision: Union[str, None] = '7e9d4180004a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recommendations', sa.Column('conversation_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_recommendations_conversation_id'), 'recommendations', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_recommendations_conversation_id'), table_name='recommendations')
    op.drop_column('recommendations', 'conversation_id')
