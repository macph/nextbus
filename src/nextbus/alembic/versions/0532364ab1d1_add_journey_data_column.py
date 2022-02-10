"""
add journey data column

Revision ID: 0532364ab1d1
Revises: de0cd0d34f8d
Create Date: 2021-10-03 14:12:51.179320

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0532364ab1d1'
down_revision = 'de0cd0d34f8d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('journey', sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    op.drop_column('journey', 'data')
