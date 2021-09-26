"""
Nullable admin area codes for postcodes

Revision ID: f543b9c57b76
Revises: a435563da77e
Create Date: 2021-09-26 15:44:14.313306

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f543b9c57b76'
down_revision = 'a435563da77e'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('postcode', 'admin_area_ref', nullable=True)


def downgrade():
    op.alter_column('postcode', 'admin_area_ref', nullable=False)
