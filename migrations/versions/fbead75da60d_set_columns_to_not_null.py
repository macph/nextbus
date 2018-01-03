"""Set columns to NOT NULL

Revision ID: fbead75da60d
Revises: 03686cae6fcb
Create Date: 2018-01-03 09:47:20.921160

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fbead75da60d'
down_revision = '03686cae6fcb'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('postcode', 'local_authority_code')
    op.drop_index('ix_stop_point_tsvector_common_name', table_name='stop_point')
    op.drop_index('ix_stop_point_common_name', table_name='stop_point')
    op.drop_column('stop_point', 'short_name')
    op.drop_column('stop_point', 'common_name')

    op.add_column('stop_point', sa.Column('name', sa.Text(), nullable=True))
    op.create_index(op.f('ix_stop_point_name'), 'stop_point', ['name'], unique=False)
    op.create_index('ix_stop_point_tsvector_name', 'stop_point',
                    [sa.text("to_tsvector('english', name)")], unique=False,
                    postgresql_using='gin')

    op.alter_column('admin_area', 'atco_code', existing_type=sa.VARCHAR(length=3),
                    nullable=False)
    op.alter_column('admin_area', 'name', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('admin_area', 'region_code', existing_type=sa.VARCHAR(length=2),
                    nullable=False)
    op.alter_column('district', 'admin_area_code', existing_type=sa.VARCHAR(length=3), 
                    nullable=False)
    op.alter_column('district', 'name', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('locality', 'admin_area_code', existing_type=sa.VARCHAR(length=3),
                    nullable=False)
    op.alter_column('locality', 'easting', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('locality', 'latitude', existing_type=postgresql.DOUBLE_PRECISION(precision=53),
                    nullable=False)
    op.alter_column('locality', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=False)
    op.alter_column('locality', 'name', existing_type=sa.TEXT(),
                    nullable=False)
    op.alter_column('locality', 'northing', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('postcode', 'admin_area_code', existing_type=sa.VARCHAR(length=3),
                    nullable=False)
    op.alter_column('postcode', 'easting', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('postcode', 'latitude', existing_type=postgresql.DOUBLE_PRECISION(precision=53),
                    nullable=False)
    op.alter_column('postcode', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=False)
    op.alter_column('postcode', 'northing', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('postcode', 'text', existing_type=sa.VARCHAR(length=8), nullable=False)
    op.alter_column('region', 'name', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('stop_area', 'admin_area_code', existing_type=sa.VARCHAR(length=3),
                    nullable=False)
    op.alter_column('stop_area', 'easting', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('stop_area', 'latitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=False)
    op.alter_column('stop_area', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=False)
    op.alter_column('stop_area', 'name', existing_type=sa.TEXT(), nullable=False)
    op.alter_column('stop_area', 'northing', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('stop_area', 'stop_area_type', existing_type=sa.VARCHAR(length=4),
                    nullable=False)
    op.alter_column('stop_point', 'admin_area_code', existing_type=sa.VARCHAR(length=3), 
                    nullable=False)
    op.alter_column('stop_point', 'easting', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('stop_point', 'indicator', existing_type=sa.TEXT(), server_default='',
                    nullable=False)
    op.alter_column('stop_point', 'latitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=False)
    op.alter_column('stop_point', 'locality_code', existing_type=sa.VARCHAR(length=8), 
                    nullable=False)
    op.alter_column('stop_point', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=False)
    op.alter_column('stop_point', 'naptan_code', existing_type=sa.VARCHAR(length=9),
                    nullable=False)
    op.alter_column('stop_point', 'northing', existing_type=sa.INTEGER(), nullable=False)
    op.alter_column('stop_point', 'short_ind', existing_type=sa.TEXT(), server_default='',
                    nullable=False)
    op.alter_column('stop_point', 'stop_type', existing_type=sa.VARCHAR(length=3), nullable=False)


def downgrade():
    op.alter_column('stop_point', 'stop_type', existing_type=sa.VARCHAR(length=3), nullable=True)
    op.alter_column('stop_point', 'short_ind', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('stop_point', 'northing', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('stop_point', 'naptan_code', existing_type=sa.VARCHAR(length=9), nullable=True)
    op.alter_column('stop_point', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=True)
    op.alter_column('stop_point', 'locality_code', existing_type=sa.VARCHAR(length=8), 
                    nullable=True)
    op.alter_column('stop_point', 'latitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=True)
    op.alter_column('stop_point', 'indicator', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('stop_point', 'easting', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('stop_point', 'admin_area_code',
                    existing_type=sa.VARCHAR(length=3), nullable=True)
    op.alter_column('stop_area', 'stop_area_type',
                    existing_type=sa.VARCHAR(length=4), nullable=True)
    op.alter_column('stop_area', 'northing', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('stop_area', 'name', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('stop_area', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=True)
    op.alter_column('stop_area', 'latitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=True)
    op.alter_column('stop_area', 'easting', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('stop_area', 'admin_area_code', existing_type=sa.VARCHAR(length=3),
                    nullable=True)
    op.alter_column('region', 'name', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('postcode', 'text', existing_type=sa.VARCHAR(length=8), nullable=True)
    op.alter_column('postcode', 'northing', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('postcode', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=True)
    op.alter_column('postcode', 'latitude', existing_type=postgresql.DOUBLE_PRECISION(precision=53),
                    nullable=True)
    op.alter_column('postcode', 'easting', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('postcode', 'admin_area_code', existing_type=sa.VARCHAR(length=3),
                    nullable=True)
    op.alter_column('locality', 'northing', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('locality', 'name', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('locality', 'longitude',
                    existing_type=postgresql.DOUBLE_PRECISION(precision=53), nullable=True)
    op.alter_column('locality', 'latitude', existing_type=postgresql.DOUBLE_PRECISION(precision=53),
                    nullable=True)
    op.alter_column('locality', 'easting', existing_type=sa.INTEGER(), nullable=True)
    op.alter_column('locality', 'admin_area_code', existing_type=sa.VARCHAR(length=3),
                    nullable=True)
    op.alter_column('district', 'name', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('district', 'admin_area_code', existing_type=sa.VARCHAR(length=3), 
                    nullable=True)
    op.alter_column('admin_area', 'region_code', existing_type=sa.VARCHAR(length=2), nullable=True)
    op.alter_column('admin_area', 'name', existing_type=sa.TEXT(), nullable=True)
    op.alter_column('admin_area', 'atco_code', existing_type=sa.VARCHAR(length=3), nullable=True)

    op.drop_index(op.f('ix_stop_point_name'), table_name='stop_point')
    op.drop_index('ix_stop_point_tsvector_name', table_name='stop_point')
    op.drop_column('stop_point', 'name')

    op.add_column('stop_point', sa.Column('common_name', sa.TEXT(), autoincrement=False,
                                          nullable=True))
    op.add_column('stop_point', sa.Column('short_name', sa.TEXT(), autoincrement=False,
                                          nullable=True))
    op.create_index('ix_stop_point_common_name', 'stop_point', ['common_name'], unique=False)
    op.create_index('ix_stop_point_tsvector_common_name', 'stop_point',
                    [sa.text("to_tsvector('english', common_name)")], unique=False,
                    postgresql_using='gin')
    op.add_column('postcode', sa.Column('local_authority_code', sa.VARCHAR(length=9),
                                        autoincrement=False, nullable=True))