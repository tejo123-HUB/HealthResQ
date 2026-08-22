"""Remove COMM-03 stub table

Revision ID: 7e9d4180004a
Revises: e6d59c8a1d31
Create Date: 2026-08-22 09:33:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7e9d4180004a'
down_revision: Union[str, None] = 'e6d59c8a1d31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(op.f('ix_comm_command_edges_from_scope_id'), table_name='comm_command_edges')
    op.drop_index(op.f('ix_comm_command_edges_to_facility_id'), table_name='comm_command_edges')
    op.drop_table('comm_command_edges')
    op.execute("DROP TYPE IF EXISTS graph_edge_type CASCADE")


def downgrade() -> None:
    op.create_table('comm_command_edges',
    sa.Column('id', postgresql.UUID(as_uuid=True), autoincrement=False, nullable=False),
    sa.Column('from_level', postgresql.ENUM('DISTRICT', 'STATE', 'NATIONAL', name='comm_issuer_level', create_type=False), autoincrement=False, nullable=False),
    sa.Column('from_scope_id', postgresql.UUID(as_uuid=True), autoincrement=False, nullable=False),
    sa.Column('to_facility_id', postgresql.UUID(as_uuid=True), autoincrement=False, nullable=False),
    sa.Column('edge_type', postgresql.ENUM('COMMAND_TO', 'ADMIN_PARENT', name='graph_edge_type'), autoincrement=False, nullable=False),
    sa.Column('enabled', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['to_facility_id'], ['facilities.id'], name='comm_command_edges_to_facility_id_fkey'),
    sa.PrimaryKeyConstraint('id', name='comm_command_edges_pkey'),
    sa.UniqueConstraint('from_level', 'from_scope_id', 'to_facility_id', 'edge_type', name='uq_comm_command_edges_edge')
    )
    op.create_index(op.f('ix_comm_command_edges_to_facility_id'), 'comm_command_edges', ['to_facility_id'], unique=False)
    op.create_index(op.f('ix_comm_command_edges_from_scope_id'), 'comm_command_edges', ['from_scope_id'], unique=False)
