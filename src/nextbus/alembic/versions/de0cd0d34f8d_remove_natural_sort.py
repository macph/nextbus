"""
remove natural sort

Revision ID: de0cd0d34f8d
Revises: 32c1e7049b33
Create Date: 2021-10-02 17:10:51.887888

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'de0cd0d34f8d'
down_revision = '32c1e7049b33'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_natural_sort_index', table_name='natural_sort')
    op.drop_table('natural_sort')

    # Create collation for natural sorting
    op.execute("CREATE COLLATION utf8_numeric (provider = icu, locale = 'en@colNumeric=yes')")
    op.alter_column('stop_point', 'short_ind', type_=sa.Text(collation='utf8_numeric'))
    op.alter_column('service', 'line', type_=sa.Text(collation='utf8_numeric'))
    op.alter_column('fts', 'indicator', type_=sa.Text(collation='utf8_numeric'))


def downgrade():
    op.alter_column('stop_point', 'short_ind', type_=sa.Text(collation='default'))
    op.alter_column('service', 'line', type_=sa.Text(collation='default'))
    op.alter_column('fts', 'indicator', type_=sa.Text(collation='default'))
    op.execute("DROP COLLATION utf8_numeric")

    op.create_table('natural_sort',
    sa.Column('string', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('index', postgresql.BYTEA(), autoincrement=False, nullable=True),
    sa.PrimaryKeyConstraint('string', name='natural_sort_pkey')
    )
    op.create_index('ix_natural_sort_index', 'natural_sort', ['index'], unique=False)
