"""added indices to fk

Revision ID: d5a745203440
Revises: 31f8bd355a5e
Create Date: 2017-12-12 08:57:55.926346

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5a745203440'
down_revision = '31f8bd355a5e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('admin_area', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admin_area_region_code'), ['region_code'], unique=False)
        batch_op.drop_index('ix_admin_area_atco_code')
        batch_op.create_unique_constraint('c_atco_code', ['atco_code'])

    with op.batch_alter_table('district', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_district_admin_area_code'), ['admin_area_code'], unique=False)

    with op.batch_alter_table('locality', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_locality_admin_area_code'), ['admin_area_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_locality_district_code'), ['district_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_locality_parent_code'), ['parent_code'], unique=False)

    with op.batch_alter_table('postcode', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_postcode_admin_area_code'), ['admin_area_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_postcode_district_code'), ['district_code'], unique=False)

    with op.batch_alter_table('stop_area', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stop_area_admin_area_code'), ['admin_area_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_stop_area_locality_code'), ['locality_code'], unique=False)

    with op.batch_alter_table('stop_point', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_stop_point_admin_area_code'), ['admin_area_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_stop_point_locality_code'), ['locality_code'], unique=False)
        batch_op.create_index(batch_op.f('ix_stop_point_stop_area_code'), ['stop_area_code'], unique=False)
        batch_op.drop_index('ix_stop_point_indicator')
        batch_op.drop_index('ix_stop_point_short_name')
        batch_op.drop_index('ix_stop_point_street')


def downgrade():
    with op.batch_alter_table('stop_point', schema=None) as batch_op:
        batch_op.create_index('ix_stop_point_street', ['street'], unique=False)
        batch_op.create_index('ix_stop_point_short_name', ['short_name'], unique=False)
        batch_op.create_index('ix_stop_point_indicator', ['indicator'], unique=False)
        batch_op.drop_index(batch_op.f('ix_stop_point_stop_area_code'))
        batch_op.drop_index(batch_op.f('ix_stop_point_locality_code'))
        batch_op.drop_index(batch_op.f('ix_stop_point_admin_area_code'))

    with op.batch_alter_table('stop_area', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stop_area_locality_code'))
        batch_op.drop_index(batch_op.f('ix_stop_area_admin_area_code'))

    with op.batch_alter_table('postcode', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_postcode_district_code'))
        batch_op.drop_index(batch_op.f('ix_postcode_admin_area_code'))

    with op.batch_alter_table('locality', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_locality_parent_code'))
        batch_op.drop_index(batch_op.f('ix_locality_district_code'))
        batch_op.drop_index(batch_op.f('ix_locality_admin_area_code'))

    with op.batch_alter_table('district', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_district_admin_area_code'))

    with op.batch_alter_table('admin_area', schema=None) as batch_op:
        batch_op.drop_constraint('c_atco_code', type_='unique')
        batch_op.create_index('ix_admin_area_atco_code', ['atco_code'], unique=1)
        batch_op.drop_index(batch_op.f('ix_admin_area_region_code'))