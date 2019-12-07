"""
add bank holiday dates for 2020

Revision ID: 39ac82acfedc
Revises: 4b9d79774675
Create Date: 2019-12-07 08:07:27.133980

"""
import datetime as dt

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39ac82acfedc'
down_revision = '4b9d79774675'
branch_labels = None
depends_on = None


bank_holiday = sa.table(
    "bank_holiday_date",
    sa.column("holiday_ref", sa.Integer),
    sa.column("date", sa.Date)
)

date_f = "%Y-%m-%d"
bank_holiday_dates = [
    {"holiday_ref": 1, "date": "2020-01-01"},
    {"holiday_ref": 2, "date": "2020-01-02"},
    {"holiday_ref": 3, "date": "2020-04-10"},
    {"holiday_ref": 4, "date": "2020-04-13"},
    {"holiday_ref": 5, "date": "2020-05-08"},
    {"holiday_ref": 6, "date": "2020-05-25"},
    {"holiday_ref": 7, "date": "2020-08-03"},
    {"holiday_ref": 8, "date": "2020-08-31"},
    {"holiday_ref": 14, "date": "2020-12-24"},
    {"holiday_ref": 9, "date": "2020-12-25"},
    {"holiday_ref": 12, "date": "2020-12-28"},
    {"holiday_ref": 15, "date": "2020-12-31"},
]


def upgrade():
    op.execute(bank_holiday.insert().values([
        {"holiday_ref": d["holiday_ref"], "date": dt.datetime.strptime(d["date"], date_f)}
        for d in bank_holiday_dates
    ]))


def downgrade():
    for d in bank_holiday_dates:
        op.execute(bank_holiday.delete().where(
            (bank_holiday.c.holiday_ref == d["holiday_ref"]) &
            (bank_holiday.c.date == d["date"])
        ))
