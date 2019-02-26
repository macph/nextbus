"""renamed operating date to excluded date

Revision ID: d26cde7b1d28
Revises: 2355305e6972
Create Date: 2019-02-26 13:24:45.674754

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd26cde7b1d28'
down_revision = '2355305e6972'
branch_labels = None
depends_on = None


operating_date = sa.table(
    'operating_date',
    sa.column('id', sa.Integer),
    sa.column('org_ref', sa.Text),
    sa.column('date', sa.Date),
    sa.column('working', sa.Boolean)
)
excluded_date = sa.table(
    'excluded_date',
    sa.column('id', sa.Integer),
    sa.column('org_ref', sa.Text),
    sa.column('date', sa.Date),
    sa.column('working', sa.Boolean)
)


def upgrade():
    op.create_table(
        'excluded_date',
        sa.Column('id', sa.Integer(), autoincrement=False, nullable=False),
        sa.Column('org_ref', sa.Text(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('working', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['org_ref'], ['organisation.code'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_excluded_date_org_ref'), 'excluded_date', ['org_ref'], unique=False)
    op.drop_index('ix_operating_date_org_ref', table_name='operating_date')
    op.execute(
        excluded_date.insert()
        .from_select([c.name for c in excluded_date.columns],
                     sa.select([operating_date.c.id, operating_date.c.org_ref,
                                operating_date.c.date, ~operating_date.c.working]))
    )
    op.drop_table('operating_date')

    op.alter_column('operating_period', 'date_end', existing_type=sa.DATE(), nullable=True)


def downgrade():
    op.create_table(
        'operating_date',
        sa.Column('id', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('org_ref', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('date', sa.DATE(), autoincrement=False, nullable=False),
        sa.Column('working', sa.BOOLEAN(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(['org_ref'], ['organisation.code'], name='operating_date_org_ref_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='operating_date_pkey')
    )
    op.create_index('ix_operating_date_org_ref', 'operating_date', ['org_ref'], unique=False)
    op.drop_index(op.f('ix_excluded_date_org_ref'), table_name='excluded_date')
    op.execute(
        operating_date.insert()
        .from_select([c.name for c in operating_date.columns],
                     sa.select([excluded_date.c.id, excluded_date.c.org_ref,
                                excluded_date.c.date, ~excluded_date.c.working]))
    )
    op.drop_table('excluded_date')

    op.alter_column('operating_period', 'date_end', existing_type=sa.DATE(), nullable=False)
