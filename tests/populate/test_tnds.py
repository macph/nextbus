"""
Testing TNDS population.
"""
import os

import lxml.etree as et
import pytest

from nextbus.populate.utils import xslt_func
from nextbus.populate.tnds import (
    bank_holidays, days_week, weeks_month, RowIds, _get_tnds_transform
)


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
TNDS_OUT = os.path.join(TEST_DIR, "TNDS_output.xml")
TNDS_RAW = os.path.join(TEST_DIR, "TNDS_raw.xml")


@pytest.mark.parametrize("days, expected", [
    ("<HolidaysOnly/>", 0),
    ("<DaysOfWeek><Monday/><Tuesday/><Wednesday/><Thursday/><Friday/>"
     "</DaysOfWeek>", 62),
    ("<DaysOfWeek><MondayToFriday/></DaysOfWeek>", 62),
    ("<DaysOfWeek><MondayToSunday/></DaysOfWeek>", 254),
    ("<DaysOfWeek><Weekend/></DaysOfWeek>", 192),
    ("<DaysOfWeek><NotSaturday/></DaysOfWeek>", 190),
    ("<DaysOfWeek><MondayToSaturday/><Saturday/></DaysOfWeek>", 126),
    (None, 62),
])
def test_days_week(days, expected):
    if days is not None:
        node = et.XML('<RegularDayType xmlns="http://www.transxchange.org.uk/">'
                      '%s</RegularDayType>' % days)
        nodes = [node]
    else:
        nodes = None

    assert days_week(None, nodes) == expected


@pytest.mark.parametrize("weeks, expected", [
    ([3], 4),
    ([1, 2, 3], 7),
    ([1, 3, 5], 21)
])
def test_weeks_month(weeks, expected):
    nodes = []
    if weeks is not None:
        week_num = ["<WeekNumber>%d</WeekNumber>" % w for w in weeks]
        weeks = "<WeekOfMonth>%s</WeekOfMonth>" % "".join(week_num)
        n = et.XML('<PeriodicDayType xmlns="http://www.transxchange.org.uk/">'
                   '%s</PeriodicDayType>' % weeks)
        nodes.append(n)

    assert weeks_month(None, nodes) == expected


@pytest.mark.parametrize("holidays, region, expected", [
    (["AllBankHolidays"], "L", 65274),
    (["AllBankHolidays"], "S", 65406),
    (["AllHolidaysExceptChristmas"], "L", 250),
    (["AllHolidaysExceptChristmas"], "S", 382),
    (["HolidayMondays"], "L", 240),
    (["HolidayMondays"], "S", 368),
    (["EasterMonday", "MayDay", "SpringBank"], "L", 112),
    (["LateSummerBankHolidayNotScotland"], "S", 0)
])
def test_bank_holidays(holidays, region, expected):
    elements = "".join("<%s/>" % h for h in holidays)
    node = et.XML("<DaysOfOperation>%s</DaysOfOperation>" % elements)
    nodes = [node]

    assert bank_holidays(None, nodes, region) == expected


def test_transform_tnds(asserts):
    transform = _get_tnds_transform()
    expected = et.parse(TNDS_OUT, parser=et.XMLParser(remove_blank_text=True))
    # Set up functions to assign IDs
    RowIds(check_existing=False)

    def always_true(_, *args):
        return True

    # Replicate functions which check for existing stops and operators
    xslt_func["stop_exists"] = always_true

    try:
        output = transform(
            et.parse(TNDS_RAW),
            region=transform.strparam("Y"),
            file=transform.strparam("TNDS_raw.xml")
        )
    except (et.XSLTApplyError, et.XSLTParseError) as err:
        for msg in getattr(err, "error_log"):
            print(msg)
        raise

    asserts.xml_elements_equal(output.getroot(), expected.getroot())
