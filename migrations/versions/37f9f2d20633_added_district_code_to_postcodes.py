"""Added district code to postcodes

Revision ID: 37f9f2d20633
Revises: 5c58a50174cd
Create Date: 2017-10-21 19:51:39.614106

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '37f9f2d20633'
down_revision = '5c58a50174cd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('Postcodes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('district_code', sa.VARCHAR(length=3), nullable=True))
        batch_op.create_foreign_key('fk_psc_district', 'Districts', ['district_code'], ['nptg_district_code'])


def downgrade():
    with op.batch_alter_table('Postcodes', schema=None) as batch_op:
        batch_op.drop_column('district_code')
        batch_op.drop_constraint('fk_psc_district', type_='foreignkey')
