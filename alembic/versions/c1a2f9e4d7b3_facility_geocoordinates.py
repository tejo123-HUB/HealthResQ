"""facilities: add latitude/longitude (OPS-01 geographic data point)

Revision ID: c1a2f9e4d7b3
Revises: 8b2738bf63dd
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a2f9e4d7b3'
down_revision: Union[str, None] = '8b2738bf63dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('facilities', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('facilities', sa.Column('longitude', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('facilities', 'longitude')
    op.drop_column('facilities', 'latitude')
