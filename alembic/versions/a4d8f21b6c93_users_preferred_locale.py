"""users: add preferred_locale (account-bound i18n language preference)

Revision ID: a4d8f21b6c93
Revises: f3a7c9e1b2d4
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d8f21b6c93'
down_revision: Union[str, None] = 'f3a7c9e1b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('preferred_locale', sa.String(), nullable=False, server_default='en'),
    )


def downgrade() -> None:
    op.drop_column('users', 'preferred_locale')
