"""initialise db again

Revision ID: a6a5182d5f4e
Revises: 
Create Date: 2017-11-13 12:07:28.933519

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6a5182d5f4e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'Regions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('region_code', sa.VARCHAR(length=2), nullable=True),
        sa.Column('region_name', sa.Text(), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('Regions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_Regions_region_code'), ['region_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_Regions_region_name'), ['region_name'], unique=False)

    op.create_table(
        'AdminAreas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('region_code', sa.VARCHAR(length=2), nullable=True),
        sa.Column('atco_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('area_name', sa.Text(), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['region_code'], ['Regions.region_code'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('AdminAreas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_AdminAreas_admin_area_code'), ['admin_area_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_AdminAreas_area_name'), ['area_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_AdminAreas_atco_area_code'), ['atco_area_code'], unique=True)

    op.create_table(
        'Districts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('district_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('district_name', sa.Text(), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['AdminAreas.admin_area_code'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('Districts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_Districts_district_code'), ['district_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_Districts_district_name'), ['district_name'], unique=False)

    op.create_table(
        'StopAreas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stop_area_code', sa.VARCHAR(length=10), nullable=True),
        sa.Column('stop_area_name', sa.Text(), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('stop_area_type', sa.VARCHAR(length=4), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['AdminAreas.admin_area_code'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('StopAreas', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_StopAreas_stop_area_code'), ['stop_area_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_StopAreas_stop_area_name'), ['stop_area_name'], unique=False)

    op.create_table(
        'Localities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('locality_code', sa.VARCHAR(length=7), nullable=True),
        sa.Column('locality_name', sa.Text(), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('district_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['AdminAreas.admin_area_code'], ),
        sa.ForeignKeyConstraint(['district_code'], ['Districts.district_code'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('Localities', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_Localities_locality_code'), ['locality_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_Localities_locality_name'), ['locality_name'], unique=False)

    op.create_table(
        'Postcodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('postcode', sa.VARCHAR(length=8), nullable=True),
        sa.Column('postcode_2', sa.VARCHAR(length=7), nullable=True),
        sa.Column('local_authority_code', sa.VARCHAR(length=9), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('district_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['AdminAreas.admin_area_code'], ),
        sa.ForeignKeyConstraint(['district_code'], ['Districts.district_code'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('Postcodes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_Postcodes_postcode'), ['postcode'], unique=True)
        batch_op.create_index(batch_op.f('ix_Postcodes_postcode_2'), ['postcode_2'], unique=True)

    op.create_table(
        'StopPoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('atco_code', sa.VARCHAR(length=12), nullable=True),
        sa.Column('naptan_code', sa.VARCHAR(length=8), nullable=True),
        sa.Column('desc_common', sa.Text(), nullable=True),
        sa.Column('desc_short', sa.Text(), nullable=True),
        sa.Column('desc_landmark', sa.Text(), nullable=True),
        sa.Column('desc_street', sa.Text(), nullable=True),
        sa.Column('desc_crossing', sa.Text(), nullable=True),
        sa.Column('desc_indicator', sa.Text(), nullable=True),
        sa.Column('desc_short_ind', sa.Text(), nullable=True),
        sa.Column('locality_code', sa.VARCHAR(length=7), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('stop_type', sa.VARCHAR(length=3), nullable=True),
        sa.Column('bearing', sa.VARCHAR(length=1), nullable=True),
        sa.Column('stop_area_code', sa.VARCHAR(length=10), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('last_modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['AdminAreas.admin_area_code'], ),
        sa.ForeignKeyConstraint(['locality_code'], ['Localities.locality_code'], ),
        sa.ForeignKeyConstraint(['stop_area_code'], ['StopAreas.stop_area_code'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('StopPoints', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_StopPoints_atco_code'), ['atco_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_StopPoints_desc_common'), ['desc_common'], unique=False)
        batch_op.create_index(batch_op.f('ix_StopPoints_desc_indicator'), ['desc_indicator'], unique=False)
        batch_op.create_index(batch_op.f('ix_StopPoints_desc_short'), ['desc_short'], unique=False)
        batch_op.create_index(batch_op.f('ix_StopPoints_desc_short_ind'), ['desc_short_ind'], unique=False)
        batch_op.create_index(batch_op.f('ix_StopPoints_desc_street'), ['desc_street'], unique=False)
        batch_op.create_index(batch_op.f('ix_StopPoints_naptan_code'), ['naptan_code'], unique=True)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('StopPoints', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_StopPoints_naptan_code'))
        batch_op.drop_index(batch_op.f('ix_StopPoints_desc_street'))
        batch_op.drop_index(batch_op.f('ix_StopPoints_desc_short_ind'))
        batch_op.drop_index(batch_op.f('ix_StopPoints_desc_short'))
        batch_op.drop_index(batch_op.f('ix_StopPoints_desc_indicator'))
        batch_op.drop_index(batch_op.f('ix_StopPoints_desc_common'))
        batch_op.drop_index(batch_op.f('ix_StopPoints_atco_code'))
    op.drop_table('StopPoints')

    with op.batch_alter_table('Postcodes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_Postcodes_postcode_2'))
        batch_op.drop_index(batch_op.f('ix_Postcodes_postcode'))
    op.drop_table('Postcodes')

    with op.batch_alter_table('Localities', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_Localities_locality_name'))
        batch_op.drop_index(batch_op.f('ix_Localities_locality_code'))
    op.drop_table('Localities')

    with op.batch_alter_table('StopAreas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_StopAreas_stop_area_name'))
        batch_op.drop_index(batch_op.f('ix_StopAreas_stop_area_code'))
    op.drop_table('StopAreas')

    with op.batch_alter_table('Districts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_Districts_district_name'))
        batch_op.drop_index(batch_op.f('ix_Districts_district_code'))
    op.drop_table('Districts')

    with op.batch_alter_table('AdminAreas', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_AdminAreas_atco_area_code'))
        batch_op.drop_index(batch_op.f('ix_AdminAreas_area_name'))
        batch_op.drop_index(batch_op.f('ix_AdminAreas_admin_area_code'))
    op.drop_table('AdminAreas')

    with op.batch_alter_table('Regions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_Regions_region_name'))
        batch_op.drop_index(batch_op.f('ix_Regions_region_code'))
    op.drop_table('Regions')

