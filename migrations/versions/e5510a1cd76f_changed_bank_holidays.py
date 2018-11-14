"""changed bank holidays

Revision ID: e5510a1cd76f
Revises: db2857ad5cdc
Create Date: 2018-11-14 16:39:09.911411

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5510a1cd76f'
down_revision = 'db2857ad5cdc'
branch_labels = None
depends_on = None


# Insert data for bank holidays
bank_holiday_dates = [
    {'holiday_ref': 13, 'date': '2017-01-02'},
    {'holiday_ref': 2, 'date': '2017-01-02'},
    {'holiday_ref': 3, 'date': '2017-04-14'},
    {'holiday_ref': 4, 'date': '2017-04-17'},
    {'holiday_ref': 5, 'date': '2017-05-01'},
    {'holiday_ref': 6, 'date': '2017-05-29'},
    {'holiday_ref': 8, 'date': '2017-08-05'},
    {'holiday_ref': 7, 'date': '2017-08-28'},
    {'holiday_ref': 9, 'date': '2017-12-25'},
    {'holiday_ref': 10, 'date': '2017-12-26'},
    {'holiday_ref': 1, 'date': '2018-01-01'},
    {'holiday_ref': 2, 'date': '2018-01-02'},
    {'holiday_ref': 3, 'date': '2018-03-30'},
    {'holiday_ref': 4, 'date': '2018-04-02'},
    {'holiday_ref': 5, 'date': '2018-05-07'},
    {'holiday_ref': 6, 'date': '2018-05-28'},
    {'holiday_ref': 8, 'date': '2018-08-06'},
    {'holiday_ref': 7, 'date': '2018-08-27'},
    {'holiday_ref': 9, 'date': '2018-12-25'},
    {'holiday_ref': 10, 'date': '2018-12-26'},
    {'holiday_ref': 1, 'date': '2019-01-01'},
    {'holiday_ref': 2, 'date': '2019-01-02'},
    {'holiday_ref': 3, 'date': '2019-04-19'},
    {'holiday_ref': 4, 'date': '2019-04-22'},
    {'holiday_ref': 5, 'date': '2019-05-06'},
    {'holiday_ref': 6, 'date': '2019-05-27'},
    {'holiday_ref': 8, 'date': '2019-08-05'},
    {'holiday_ref': 7, 'date': '2019-08-26'},
    {'holiday_ref': 9, 'date': '2019-12-25'},
    {'holiday_ref': 10, 'date': '2019-12-26'},
]


def upgrade():
    bh_dates = sa.table(
        'bank_holiday_date',
        sa.Column('holiday_ref', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
    )
    op.bulk_insert(bh_dates, bank_holiday_dates)

    op.add_column('bank_holidays', sa.Column('holidays', sa.Integer(), autoincrement=False, nullable=False))
    op.create_index(op.f('ix_bank_holidays_holidays'), 'bank_holidays', ['holidays'], unique=False)
    op.drop_index('ix_bank_holidays_holiday_ref', table_name='bank_holidays')
    op.drop_constraint('bank_holidays_holiday_ref_fkey', 'bank_holidays', type_='foreignkey')
    op.drop_column('bank_holidays', 'holiday_ref')
    op.drop_index('ix_journey_service_ref', table_name='journey')
    op.drop_constraint('journey_service_ref_fkey', 'journey', type_='foreignkey')
    op.drop_column('journey', 'service_ref')


def downgrade():
    op.add_column('journey', sa.Column('service_ref', sa.Text(), autoincrement=False, nullable=False))
    op.create_foreign_key('journey_service_ref_fkey', 'journey', 'service', ['service_ref'], ['code'], ondelete='CASCADE')
    op.create_index('ix_journey_service_ref', 'journey', ['service_ref'], unique=False)
    op.add_column('bank_holidays', sa.Column('holiday_ref', sa.Integer(), autoincrement=False, nullable=False))
    op.create_foreign_key('bank_holidays_holiday_ref_fkey', 'bank_holidays', 'bank_holiday', ['holiday_ref'], ['id'])
    op.create_index('ix_bank_holidays_holiday_ref', 'bank_holidays', ['holiday_ref'], unique=False)
    op.drop_index(op.f('ix_bank_holidays_holidays'), table_name='bank_holidays')
    op.drop_column('bank_holidays', 'holidays')
