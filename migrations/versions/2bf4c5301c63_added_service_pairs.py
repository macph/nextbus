"""
added service pairs

Revision ID: 2bf4c5301c63
Revises: b0f39159c982
Create Date: 2019-07-18 19:03:26.789713

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2bf4c5301c63'
down_revision = 'b0f39159c982'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'service_pair',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('service0', sa.Integer(), nullable=False),
        sa.Column('direction0', sa.Boolean(), nullable=False),
        sa.Column('count0', sa.Integer(), nullable=False),
        sa.Column('service1', sa.Integer(), nullable=False),
        sa.Column('direction1', sa.Boolean(), nullable=False),
        sa.Column('count1', sa.Integer(), nullable=False),
        sa.Column('similarity', sa.Float(), nullable=False),
        sa.CheckConstraint('service0 < service1'),
        sa.ForeignKeyConstraint(('service0',), ['service.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(('service1',), ['service.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_service_pair_direction0'), 'service_pair', ['direction0'], unique=False)
    op.create_index(op.f('ix_service_pair_direction1'), 'service_pair', ['direction1'], unique=False)
    op.create_index(op.f('ix_service_pair_service0'), 'service_pair', ['service0'], unique=False)
    op.create_index(op.f('ix_service_pair_service1'), 'service_pair', ['service1'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_service_pair_service1'), table_name='service_pair')
    op.drop_index(op.f('ix_service_pair_service0'), table_name='service_pair')
    op.drop_index(op.f('ix_service_pair_direction1'), table_name='service_pair')
    op.drop_index(op.f('ix_service_pair_direction0'), table_name='service_pair')
    op.drop_table('service_pair')
