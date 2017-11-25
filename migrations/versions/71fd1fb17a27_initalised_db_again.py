"""initalised db again

Revision ID: 71fd1fb17a27
Revises: 
Create Date: 2017-11-25 19:19:56.728604

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '71fd1fb17a27'
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
    with op.batch_alter_table('region', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_region_name'), ['name'], unique=False)

    op.create_table(
        'admin_area',
        sa.Column('code', sa.VARCHAR(length=3), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('atco_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('region_code', sa.VARCHAR(length=2), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['region_code'], ['region.code'], ),
        sa.PrimaryKeyConstraint('code')
    )
    with op.batch_alter_table('admin_area', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admin_area_atco_code'), ['atco_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_admin_area_name'), ['name'], unique=False)

    op.create_table(
        'district',
        sa.Column('code', sa.VARCHAR(length=3), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ),
        sa.PrimaryKeyConstraint('code')
    )
    with op.batch_alter_table('district', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_district_name'), ['name'], unique=False)

    op.create_table(
        'stop_area',
        sa.Column('code', sa.VARCHAR(length=10), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('stop_area_type', sa.VARCHAR(length=4), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ),
        sa.PrimaryKeyConstraint('code')
    )
    with op.batch_alter_table('stop_area', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stop_area_name'), ['name'], unique=False)

    op.create_table(
        'locality',
        sa.Column('code', sa.VARCHAR(length=7), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('parent_code', sa.VARCHAR(length=7), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('district_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ),
        sa.ForeignKeyConstraint(['district_code'], ['district.code'], ),
        sa.ForeignKeyConstraint(['parent_code'], ['locality.code'], ),
        sa.PrimaryKeyConstraint('code')
    )
    with op.batch_alter_table('locality', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_locality_name'), ['name'], unique=False)

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
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ),
        sa.ForeignKeyConstraint(['district_code'], ['district.code'], ),
        sa.PrimaryKeyConstraint('index')
    )
    with op.batch_alter_table('postcode', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_postcode_text'), ['text'], unique=True)

    op.create_table(
        'stop_point',
        sa.Column('atco_code', sa.VARCHAR(length=12), nullable=False),
        sa.Column('naptan_code', sa.VARCHAR(length=8), nullable=True),
        sa.Column('common_name', sa.Text(), nullable=True),
        sa.Column('short_name', sa.Text(), nullable=True),
        sa.Column('landmark', sa.Text(), nullable=True),
        sa.Column('street', sa.Text(), nullable=True),
        sa.Column('crossing', sa.Text(), nullable=True),
        sa.Column('indicator', sa.Text(), nullable=True),
        sa.Column('short_ind', sa.Text(), nullable=True),
        sa.Column('locality_code', sa.VARCHAR(length=7), nullable=True),
        sa.Column('admin_area_code', sa.VARCHAR(length=3), nullable=True),
        sa.Column('stop_area_code', sa.VARCHAR(length=10), nullable=True),
        sa.Column('easting', sa.Integer(), nullable=True),
        sa.Column('northing', sa.Integer(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('stop_type', sa.VARCHAR(length=3), nullable=True),
        sa.Column('bearing', sa.VARCHAR(length=1), nullable=True),
        sa.Column('modified', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['admin_area_code'], ['admin_area.code'], ),
        sa.ForeignKeyConstraint(['locality_code'], ['locality.code'], ),
        sa.ForeignKeyConstraint(['stop_area_code'], ['stop_area.code'], ),
        sa.PrimaryKeyConstraint('atco_code')
    )
    with op.batch_alter_table('stop_point', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stop_point_common_name'), ['common_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_stop_point_indicator'), ['indicator'], unique=False)
        batch_op.create_index(batch_op.f('ix_stop_point_naptan_code'), ['naptan_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_stop_point_short_ind'), ['short_ind'], unique=False)
        batch_op.create_index(batch_op.f('ix_stop_point_short_name'), ['short_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_stop_point_street'), ['street'], unique=False)


def downgrade():
    with op.batch_alter_table('stop_point', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stop_point_street'))
        batch_op.drop_index(batch_op.f('ix_stop_point_short_name'))
        batch_op.drop_index(batch_op.f('ix_stop_point_short_ind'))
        batch_op.drop_index(batch_op.f('ix_stop_point_naptan_code'))
        batch_op.drop_index(batch_op.f('ix_stop_point_indicator'))
        batch_op.drop_index(batch_op.f('ix_stop_point_common_name'))

    op.drop_table('stop_point')
    with op.batch_alter_table('postcode', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_postcode_text'))

    op.drop_table('postcode')
    with op.batch_alter_table('locality', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_locality_name'))

    op.drop_table('locality')
    with op.batch_alter_table('stop_area', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stop_area_name'))

    op.drop_table('stop_area')
    with op.batch_alter_table('district', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_district_name'))

    op.drop_table('district')
    with op.batch_alter_table('admin_area', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_area_name'))
        batch_op.drop_index(batch_op.f('ix_admin_area_atco_code'))

    op.drop_table('admin_area')
    with op.batch_alter_table('region', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_region_name'))

    op.drop_table('region')
