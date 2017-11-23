"""added parent localities

Revision ID: 8f5c25301bb3
Revises: a6a5182d5f4e
Create Date: 2017-11-23 19:46:03.410663

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f5c25301bb3'
down_revision = 'a6a5182d5f4e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('Localities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parent_locality_code', sa.VARCHAR(length=7), nullable=True))
        batch_op.create_foreign_key('fk_localities', 'Localities', ['parent_locality_code'], ['locality_code'])

def downgrade():
    with op.batch_alter_table('Localities', schema=None) as batch_op:
        batch_op.drop_constraint('fk_localities', type_='foreignkey')
        batch_op.drop_column('parent_locality_code')
