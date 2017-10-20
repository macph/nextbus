"""Added indices

Revision ID: 5c58a50174cd
Revises: 54d67d76f3db
Create Date: 2017-10-20 09:39:37.370705

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5c58a50174cd'
down_revision = '54d67d76f3db'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_AdminAreas_area_name'), 'AdminAreas', ['area_name'], unique=False)
    op.create_index(op.f('ix_Districts_district_name'), 'Districts', ['district_name'], unique=False)
    op.create_index(op.f('ix_Localities_locality_name'), 'Localities', ['locality_name'], unique=False)
    op.create_index(op.f('ix_Postcodes_postcode_2'), 'Postcodes', ['postcode_2'], unique=True)
    op.create_index(op.f('ix_Regions_region_name'), 'Regions', ['region_name'], unique=False)
    op.create_index(op.f('ix_StopAreas_stop_area_name'), 'StopAreas', ['stop_area_name'], unique=False)
    op.create_index(op.f('ix_StopPoints_desc_common'), 'StopPoints', ['desc_common'], unique=False)
    op.create_index(op.f('ix_StopPoints_desc_indicator'), 'StopPoints', ['desc_indicator'], unique=False)
    op.create_index(op.f('ix_StopPoints_desc_short'), 'StopPoints', ['desc_short'], unique=False)
    op.create_index(op.f('ix_StopPoints_desc_street'), 'StopPoints', ['desc_street'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_StopPoints_desc_street'), table_name='StopPoints')
    op.drop_index(op.f('ix_StopPoints_desc_short'), table_name='StopPoints')
    op.drop_index(op.f('ix_StopPoints_desc_indicator'), table_name='StopPoints')
    op.drop_index(op.f('ix_StopPoints_desc_common'), table_name='StopPoints')
    op.drop_index(op.f('ix_StopAreas_stop_area_name'), table_name='StopAreas')
    op.drop_index(op.f('ix_Regions_region_name'), table_name='Regions')
    op.drop_index(op.f('ix_Postcodes_postcode_2'), table_name='Postcodes')
    op.drop_index(op.f('ix_Localities_locality_name'), table_name='Localities')
    op.drop_index(op.f('ix_Districts_district_name'), table_name='Districts')
    op.drop_index(op.f('ix_AdminAreas_area_name'), table_name='AdminAreas')
