"""
modified constraints for operating and special periods

Revision ID: 3af2db23aaf3
Revises: 7302c53aedb9
Create Date: 2019-05-18 11:11:28.168385

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3af2db23aaf3'
down_revision = '2c4c58e49aa5'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('operating_period_check', 'operating_period')
    op.drop_constraint('special_period_check', 'special_period')
    op.alter_column('special_period', 'date_end', existing_type=sa.DATE(), nullable=False)
    op.alter_column('special_period', 'date_start', existing_type=sa.DATE(), nullable=False)


def downgrade():
    op.alter_column('special_period', 'date_start', existing_type=sa.DATE(), nullable=True)
    op.alter_column('special_period', 'date_end', existing_type=sa.DATE(), nullable=True)
    op.create_check_constraint('operating_period_check', 'operating_period', sa.column('date_start') <= sa.column('date_end'))
    op.create_check_constraint('special_period_check', 'special_period', sa.column('date_start') <= sa.column('date_end'))
