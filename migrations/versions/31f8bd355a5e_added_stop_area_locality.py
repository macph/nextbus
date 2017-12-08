"""added stop area locality

Revision ID: 31f8bd355a5e
Revises: 71fd1fb17a27
Create Date: 2017-12-08 14:47:19.792904

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '31f8bd355a5e'
down_revision = '71fd1fb17a27'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('admin_area', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_live', sa.Boolean(), nullable=True))

    with op.batch_alter_table('stop_area', schema=None) as batch_op:
        batch_op.add_column(sa.Column('locality_code', sa.VARCHAR(length=7), nullable=True))
        batch_op.create_foreign_key('fk_sa_locality', 'locality', ['locality_code'], ['code'])


def downgrade():
    with op.batch_alter_table('stop_area', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sa_locality', type_='foreignkey')
        batch_op.drop_column('locality_code')

    with op.batch_alter_table('admin_area', schema=None) as batch_op:
        batch_op.drop_column('is_live')