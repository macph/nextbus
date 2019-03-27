"""
fk for region on journey pattern

Revision ID: fe9548df3474
Revises: 74069f6388f3
Create Date: 2019-03-27 09:15:14.702167

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fe9548df3474'
down_revision = '74069f6388f3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_foreign_key(op.f('journey_pattern_region_ref_fkey'), 'journey_pattern', 'region', ['region_ref'], ['code'], ondelete='CASCADE')


def downgrade():
    op.drop_constraint(op.f('journey_pattern_region_ref_fkey'), 'journey_pattern', type_='foreignkey')
