"""
Nullable origin and destination for journey patterns

Revision ID: 32c1e7049b33
Revises: f543b9c57b76
Create Date: 2021-09-26 16:39:29.078848

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '32c1e7049b33'
down_revision = 'f543b9c57b76'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('journey_pattern', 'origin', nullable=True)
    op.alter_column('journey_pattern', 'destination', nullable=True)


def downgrade():
    op.alter_column('journey_pattern', 'destination', nullable=False)
    op.alter_column('journey_pattern', 'origin', nullable=False)
