"""added GIN indices

Revision ID: 03686cae6fcb
Revises: ca24f7a0a83e
Create Date: 2017-12-21 09:29:38.383001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '03686cae6fcb'
down_revision = 'ca24f7a0a83e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_region_tsvector_name', 'region', [sa.text("to_tsvector('english', name)")], unique=False, postgresql_using='gin')
    op.create_index('ix_admin_area_tsvector_name', 'admin_area', [sa.text("to_tsvector('english', name)")], unique=False, postgresql_using='gin')
    op.create_index('ix_district_tsvector_name', 'district', [sa.text("to_tsvector('english', name)")], unique=False, postgresql_using='gin')
    op.create_index('ix_locality_tsvector_name', 'locality', [sa.text("to_tsvector('english', name)")], unique=False, postgresql_using='gin')
    op.create_index('ix_stop_area_tsvector_name', 'stop_area', [sa.text("to_tsvector('english', name)")], unique=False, postgresql_using='gin')
    op.create_index('ix_stop_point_tsvector_common_name_street', 'stop_point', [sa.text("to_tsvector('english', common_name || ' ' || street)")], unique=False, postgresql_using='gin')


def downgrade():
    op.drop_index('ix_region_tsvector_name', table_name='region')
    op.drop_index('ix_admin_area_tsvector_name', table_name='admin_area')
    op.drop_index('ix_district_tsvector_name', table_name='district')
    op.drop_index('ix_locality_tsvector_name', table_name='locality')
    op.drop_index('ix_stop_area_tsvector_name', table_name='stop_area')
    op.drop_index('ix_stop_point_tsvector_common_name_street', table_name='stop_point')
