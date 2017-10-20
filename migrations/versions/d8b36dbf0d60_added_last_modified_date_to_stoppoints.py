"""Added last modified date to StopPoints

Revision ID: d8b36dbf0d60
Revises: 37f9f2d20633
Create Date: 2017-10-24 09:08:47.494875

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8b36dbf0d60'
down_revision = '37f9f2d20633'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('StopPoints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_modified', sa.DateTime(), nullable=True))

def downgrade():
    with op.batch_alter_table('StopPoints', schema=None) as batch_op:
        batch_op.drop_column('last_modified')