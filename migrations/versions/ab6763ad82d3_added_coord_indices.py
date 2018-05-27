"""added coord indices

Revision ID: ab6763ad82d3
Revises: f88d5245a532
Create Date: 2018-05-27 10:09:20.074300

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab6763ad82d3'
down_revision = 'f88d5245a532'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(op.f('ix_stop_point_latitude'), 'stop_point', ['latitude'], unique=False)
    op.create_index(op.f('ix_stop_point_longitude'), 'stop_point', ['longitude'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_stop_point_longitude'), table_name='stop_point')
    op.drop_index(op.f('ix_stop_point_latitude'), table_name='stop_point')
