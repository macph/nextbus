"""
moved bank holiday data within journeys

Revision ID: a435563da77e
Revises: 0d7fbd9b8750
Create Date: 2019-12-16 17:56:59.054996

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a435563da77e'
down_revision = '0d7fbd9b8750'
branch_labels = None
depends_on = None


journey = sa.table(
    "journey",
    sa.column("id", sa.Integer),
    sa.column("exclude_holidays", sa.Integer),
    sa.column("include_holidays", sa.Integer)
)
bank_holidays = sa.table(
    "bank_holidays",
    sa.column("holidays", sa.Integer),
    sa.column("journey_ref", sa.Integer),
    sa.column("operational", sa.Boolean)
)


def update_journey_holidays():
    include = bank_holidays.alias("inc_h")
    exclude = bank_holidays.alias("exc_h")

    journey_holidays = (
        sa.select([
            journey.c.id.label("id"),
            sa.func.coalesce(include.c.holidays, 0).label("include_holidays"),
            sa.func.coalesce(exclude.c.holidays, 0).label("exclude_holidays")
        ])
        .select_from(
            journey
            .outerjoin(include, (journey.c.id == include.c.journey_ref) &
                       include.c.operational)
            .outerjoin(exclude, (journey.c.id == exclude.c.journey_ref) &
                       ~exclude.c.operational)
        )
        .alias("t")
    )

    return (
        sa.update(journey)
        .values(
            include_holidays=journey_holidays.c.include_holidays,
            exclude_holidays=journey_holidays.c.exclude_holidays
        )
        .where(journey.c.id == journey_holidays.c.id)
    )


def insert_bank_holidays(operational):
    status = sa.true() if operational else sa.false()
    column_name = "include_holidays" if operational else "exclude_holidays"
    holidays_column = journey.c[column_name]

    return (
        sa.insert(bank_holidays)
        .from_select(
            ["holidays", "journey_ref", "operational"],
            sa.select([
                holidays_column.label("holidays"),
                journey.c.id.label("journey_ref"),
                status.c.label("operational")
            ])
            .where(holidays_column != 0)
        )
    )


def upgrade():
    op.add_column('journey', sa.Column('exclude_holidays', sa.Integer(), nullable=True))
    op.add_column('journey', sa.Column('include_holidays', sa.Integer(), nullable=True))

    op.execute(update_journey_holidays())
    op.alter_column('journey', 'exclude_holidays', nullable=False)
    op.alter_column('journey', 'include_holidays', nullable=False)

    op.drop_index('ix_bank_holidays_holidays', table_name='bank_holidays')
    op.drop_index('ix_bank_holidays_journey_ref', table_name='bank_holidays')
    op.drop_table('bank_holidays')


def downgrade():
    op.create_table(
        'bank_holidays',
        sa.Column('holidays', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('journey_ref', sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('operational', sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(('journey_ref',), ['journey.id'], name='bank_holidays_journey_ref_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('holidays', 'journey_ref', name='bank_holidays_pkey')
    )
    op.create_index('ix_bank_holidays_journey_ref', 'bank_holidays', ['journey_ref'], unique=False)
    op.create_index('ix_bank_holidays_holidays', 'bank_holidays', ['holidays'], unique=False)

    op.execute(insert_bank_holidays(False))
    op.execute(insert_bank_holidays(True))

    op.drop_column('journey', 'include_holidays')
    op.drop_column('journey', 'exclude_holidays')
