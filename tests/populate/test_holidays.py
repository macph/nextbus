import datetime
import os

import pytest

from nextbus import db, models
from nextbus.populate.holidays import populate_holiday_data

TEST_DIR = os.path.dirname(os.path.realpath(__file__))
BANK_HOLIDAYS_JSON = os.path.join(TEST_DIR, "bank_holidays.json")


@pytest.fixture
def create_db_with_holidays(create_db):
    with db.engine.begin() as connection:
        populate_holiday_data(connection, BANK_HOLIDAYS_JSON)


def test_commit_holiday_data(create_db_with_holidays):
    assert models.BankHolidayDate.query.count() == 41


def test_holiday_data_new_years_day_substitute(create_db_with_holidays):
    date = (
        models.BankHolidayDate.query
        .filter(models.BankHolidayDate.holiday_ref == 13)
        .order_by(models.BankHolidayDate.date)
        .one()
    )
    # There will be a substitute NYD in 2022.
    assert date.date == datetime.date(2022, 1, 3)


@pytest.mark.parametrize("holiday_ref", [7, 8])
def test_holiday_data_summer(create_db_with_holidays, holiday_ref):
    dates = (
        models.BankHolidayDate.query
        .filter(models.BankHolidayDate.holiday_ref == holiday_ref)
        .order_by(models.BankHolidayDate.date)
        .all()
    )
    # 3 summer bank holidays inside and outside Scotland
    assert len(dates) == 3


@pytest.mark.parametrize("holiday_ref", [1, 9, 10, 14, 15])
def test_holiday_data_annual(create_db_with_holidays, holiday_ref):
    dates = (
        models.BankHolidayDate.query
        .filter(models.BankHolidayDate.holiday_ref == holiday_ref)
        .order_by(models.BankHolidayDate.date)
        .all()
    )
    # Expect dates from 2020-22 only, and all of them on the same day.
    assert all(
        (dates[0].date.month, dates[0].date.day) == (d.date.month, d.date.day)
        for d in dates[1:]
    )


def test_holiday_data_ve_day(create_db_with_holidays):
    # May Day in 2020 was marked as VE day; this should still be read as MayDay
    ve_day = (
        models.BankHolidayDate.query
        .filter(models.BankHolidayDate.date == datetime.date(2020, 5, 8))
        .one()
    )
    assert ve_day.holiday_ref == 5
