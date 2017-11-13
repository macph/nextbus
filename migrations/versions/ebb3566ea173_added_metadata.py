"""added metadata

Revision ID: ebb3566ea173
Revises: a6a5182d5f4e
Create Date: 2017-11-13 13:17:31.567388

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ebb3566ea173'
down_revision = 'a6a5182d5f4e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'Meta',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('atco_areas', sa.Text(), nullable=True),
        sa.Column('naptan_last_modified', sa.DateTime(), nullable=True),
        sa.Column('nptg_last_modified', sa.DateTime(), nullable=True),
        sa.Column('nspl_last_modified', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('Meta')
