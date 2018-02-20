"""added tsvector columns

Revision ID: 295e6c3d42b9
Revises: 2f1d6aa8c56f
Create Date: 2018-02-19 11:02:04.814264

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '295e6c3d42b9'
down_revision = '2f1d6aa8c56f'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_region_tsvector_name', table_name='region')
    op.add_column('region', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_region_tsvector_name', 'region', ['tsv_name'], unique=False, postgresql_using='gin')

    op.drop_index('ix_admin_area_tsvector_name', table_name='admin_area')
    op.add_column('admin_area', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_admin_area_tsvector_name', 'admin_area', ['tsv_name'], unique=False, postgresql_using='gin')

    op.drop_index('ix_district_tsvector_name', table_name='district')
    op.add_column('district', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_district_tsvector_name', 'district', ['tsv_name'], unique=False, postgresql_using='gin')

    op.drop_index('ix_locality_tsvector_name', table_name='locality')
    op.add_column('locality', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_locality_tsvector_name', 'locality', ['tsv_name'], unique=False, postgresql_using='gin')

    op.drop_index('ix_stop_area_tsvector_name', table_name='stop_area')
    op.add_column('stop_area', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_stop_area_tsvector_name', 'stop_area', ['tsv_name'], unique=False, postgresql_using='gin')

    op.drop_index('ix_stop_point_tsvector_name', table_name='stop_point')
    op.drop_index('ix_stop_point_tsvector_street', table_name='stop_point')
    op.add_column('stop_point', sa.Column('tsv_both', postgresql.TSVECTOR(), nullable=True))
    op.add_column('stop_point', sa.Column('tsv_name', postgresql.TSVECTOR(), nullable=True))
    op.add_column('stop_point', sa.Column('tsv_street', postgresql.TSVECTOR(), nullable=True))
    op.create_index('ix_stop_point_tsvector_both', 'stop_point', ['tsv_both'], unique=False, postgresql_using='gin')
    op.create_index('ix_stop_point_tsvector_name', 'stop_point', ['tsv_name'], unique=False, postgresql_using='gin')
    op.create_index('ix_stop_point_tsvector_street', 'stop_point', ['tsv_street'], unique=False, postgresql_using='gin')


def downgrade():
    op.drop_index('ix_stop_point_tsvector_street', table_name='stop_point')
    op.drop_index('ix_stop_point_tsvector_name', table_name='stop_point')
    op.drop_index('ix_stop_point_tsvector_both', table_name='stop_point')
    op.drop_column('stop_point', 'tsv_street')
    op.drop_column('stop_point', 'tsv_name')
    op.drop_column('stop_point', 'tsv_both')
    op.create_index('ix_stop_point_tsvector_street', 'stop_point',
                    [sa.text("to_tsvector('english', street)")], unique=False,
                    postgresql_using='gin')
    op.create_index('ix_stop_point_tsvector_name', 'stop_point',
                    [sa.text("to_tsvector('english', name)")], unique=False,
                    postgresql_using='gin')

    op.drop_index('ix_stop_area_tsvector_name', table_name='stop_area')
    op.drop_column('stop_area', 'tsv_name')
    op.create_index('ix_stop_area_tsvector_name', 'stop_area',
                    [sa.text("to_tsvector('english', name)")], unique=False,
                    postgresql_using='gin')

    op.drop_index('ix_locality_tsvector_name', table_name='locality')
    op.drop_column('locality', 'tsv_name')
    op.create_index('ix_locality_tsvector_name', 'locality',
                    [sa.text("to_tsvector('english', name)")], unique=False,
                    postgresql_using='gin')

    op.drop_index('ix_district_tsvector_name', table_name='district')
    op.drop_column('district', 'tsv_name')
    op.create_index('ix_district_tsvector_name', 'district',
                    [sa.text("to_tsvector('english', name)")], unique=False,
                    postgresql_using='gin')

    op.drop_index('ix_admin_area_tsvector_name', table_name='admin_area')
    op.drop_column('admin_area', 'tsv_name')
    op.create_index('ix_admin_area_tsvector_name', 'admin_area',
                    [sa.text("to_tsvector('english', name)")], unique=False,
                    postgresql_using='gin')

    op.drop_index('ix_region_tsvector_name', table_name='region')
    op.drop_column('region', 'tsv_name')
    op.create_index('ix_region_tsvector_name', 'region',
                    [sa.text("to_tsvector('english', name)")],
                    unique=False, postgresql_using='gin')
