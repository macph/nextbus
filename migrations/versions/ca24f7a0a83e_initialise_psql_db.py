"""initialise psql db

Revision ID: ca24f7a0a83e
Revises: 
Create Date: 2017-12-13 10:50:24.689753

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ca24f7a0a83e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'region',
        sa.Column('code', sa.VARCHAR(length=2), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('code')
    )
    op.create_index(op.f('ix_region_name'), 'region', ['name'], unique=False)
    op.create_table(
        'admin_area',
        sa.Column('code', sa.VARCHAR(length=3), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('atco_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('region_code', sa.VARCHAR(length=2), nullable=True),
        sa.Column('is_live', sa.Boolean(), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['region_code'], ['region.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('code'),
        sa.UniqueConstraint('atco_code')
    )
    op.create_index(op.f('ix_admin_area_name'), 'admin_area', ['name'], unique=False)
    op.create_index(op.f('ix_admin_area_region_code'), 'admin_area', ['region_code'], unique=False)
    op.create_table(
        'district',
        sa.Column('code', sa.VARCHAR(length=3), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('code')
    )
    op.create_index(op.f('ix_district_admin_area_code'), 'district', ['admin_area_code'], unique=False)
    op.create_index(op.f('ix_district_name'), 'district', ['name'], unique=False)
    op.create_table(
        'locality',
        sa.Column('code', sa.VARCHAR(length=8), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('parent_code', sa.VARCHAR(length=8), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('district_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['district_code'], ['district.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('code')
    )
    op.create_index(op.f('ix_locality_admin_area_code'), 'locality', ['admin_area_code'], unique=False)
    op.create_index(op.f('ix_locality_district_code'), 'locality', ['district_code'], unique=False)
    op.create_index(op.f('ix_locality_name'), 'locality', ['name'], unique=False)
    op.create_index(op.f('ix_locality_parent_code'), 'locality', ['parent_code'], unique=False)
    op.create_table(
        'postcode',
        sa.Column('index', sa.VARCHAR(length=7), nullable=False),
        sa.Column('text', sa.VARCHAR(length=8), nullable=True),
        sa.Column('local_authority_code', sa.VARCHAR(length=9), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('district_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['district_code'], ['district.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('index')
    )
    op.create_index(op.f('ix_postcode_admin_area_code'), 'postcode', ['admin_area_code'], unique=False)
    op.create_index(op.f('ix_postcode_district_code'), 'postcode', ['district_code'], unique=False)
    op.create_index(op.f('ix_postcode_text'), 'postcode', ['text'], unique=True)
    op.create_table(
        'stop_area',
        sa.Column('code', sa.VARCHAR(length=12), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('locality_code', sa.VARCHAR(length=8), nullable=True),
        sa.Column('stop_area_type', sa.VARCHAR(length=4), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['locality_code'], ['locality.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('code')
    )
    op.create_index(op.f('ix_stop_area_admin_area_code'), 'stop_area', ['admin_area_code'], unique=False)
    op.create_index(op.f('ix_stop_area_locality_code'), 'stop_area', ['locality_code'], unique=False)
    op.create_index(op.f('ix_stop_area_name'), 'stop_area', ['name'], unique=False)
    op.create_table(
        'stop_point',
        sa.Column('atco_code', sa.VARCHAR(length=12), nullable=False),
        sa.Column('naptan_code', sa.VARCHAR(length=9), nullable=True),
        sa.Column('common_name', sa.Text(), nullable=True),
        sa.Column('short_name', sa.Text(), nullable=True),
        sa.Column('landmark', sa.Text(), nullable=True),
        sa.Column('street', sa.Text(), nullable=True),
        sa.Column('crossing', sa.Text(), nullable=True),
        sa.Column('indicator', sa.Text(), nullable=True),
        sa.Column('short_ind', sa.Text(), nullable=True),
        sa.Column('locality_code', sa.VARCHAR(length=8), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('stop_area_code', sa.VARCHAR(length=12), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('stop_type', sa.VARCHAR(length=3), nullable=True),
        sa.Column('bearing', sa.VARCHAR(length=2), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['locality_code'], ['locality.code'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stop_area_code'], ['stop_area.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('atco_code')
    )
    op.create_index(op.f('ix_stop_point_admin_area_code'), 'stop_point', ['admin_area_code'], unique=False)
    op.create_index(op.f('ix_stop_point_common_name'), 'stop_point', ['common_name'], unique=False)
    op.create_index(op.f('ix_stop_point_locality_code'), 'stop_point', ['locality_code'], unique=False)
    op.create_index(op.f('ix_stop_point_naptan_code'), 'stop_point', ['naptan_code'], unique=True)
    op.create_index(op.f('ix_stop_point_short_ind'), 'stop_point', ['short_ind'], unique=False)
    op.create_index(op.f('ix_stop_point_stop_area_code'), 'stop_point', ['stop_area_code'], unique=False)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_stop_point_stop_area_code'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_short_ind'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_naptan_code'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_locality_code'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_common_name'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_admin_area_code'), table_name='stop_point')
    op.drop_table('stop_point')
    op.drop_index(op.f('ix_stop_area_name'), table_name='stop_area')
    op.drop_index(op.f('ix_stop_area_locality_code'), table_name='stop_area')
    op.drop_index(op.f('ix_stop_area_admin_area_code'), table_name='stop_area')
    op.drop_table('stop_area')
    op.drop_index(op.f('ix_postcode_text'), table_name='postcode')
    op.drop_index(op.f('ix_postcode_district_code'), table_name='postcode')
    op.drop_index(op.f('ix_postcode_admin_area_code'), table_name='postcode')
    op.drop_table('postcode')
    op.drop_index(op.f('ix_locality_parent_code'), table_name='locality')
    op.drop_index(op.f('ix_locality_name'), table_name='locality')
    op.drop_index(op.f('ix_locality_district_code'), table_name='locality')
    op.drop_index(op.f('ix_locality_admin_area_code'), table_name='locality')
    op.drop_table('locality')
    op.drop_index(op.f('ix_district_name'), table_name='district')
    op.drop_index(op.f('ix_district_admin_area_code'), table_name='district')
    op.drop_table('district')
    op.drop_index(op.f('ix_admin_area_region_code'), table_name='admin_area')
    op.drop_index(op.f('ix_admin_area_name'), table_name='admin_area')
    op.drop_table('admin_area')
    op.drop_index(op.f('ix_region_name'), table_name='region')
    op.drop_table('region')
    # ### end Alembic commands ###
