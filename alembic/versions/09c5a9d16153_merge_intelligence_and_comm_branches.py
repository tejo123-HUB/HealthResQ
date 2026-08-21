"""merge intelligence and comm branches

Revision ID: 09c5a9d16153
Revises: c1a2f9e4d7b3, c3f1a9d2b7e4
Create Date: 2026-08-21 15:19:26.557000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09c5a9d16153'
down_revision: Union[str, None] = ('c1a2f9e4d7b3', 'c3f1a9d2b7e4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
