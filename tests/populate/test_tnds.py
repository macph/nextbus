"""
Testing TNDS population.
"""
import datetime
from importlib.resources import open_binary
import os

import lxml.etree as et
import pytest

from nextbus import models
from nextbus.populate.utils import (
    collect_xml_data, populate_database, xslt_func, xslt_transform
)
from nextbus.populate.tnds import (
    bank_holidays, days_week, weeks_month, format_description,
    setup_tnds_functions, short_description, ServiceCodes, RowIds
)


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
TNDS_OUT = os.path.join(TEST_DIR, "TNDS_data.xml")
TNDS_RAW = os.path.join(TEST_DIR, "TNDS_test.xml")
TNDS_DSM = os.path.join(TEST_DIR, "TNDS_DSM.xml")


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
        node = et.XML(
            f'<RegularDayType xmlns="http://www.transxchange.org.uk/">{days}'
            f'</RegularDayType>'
        )
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
        week_num = [f"<WeekNumber>{w}</WeekNumber>" for w in weeks]
        weeks = f"<WeekOfMonth>{''.join(week_num)}</WeekOfMonth>"
        n = et.XML(
            f'<PeriodicDayType xmlns="http://www.transxchange.org.uk/">{weeks}'
            '</PeriodicDayType>'
        )
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
    elements = "".join(f"<{h}/>" for h in holidays)
    node = et.XML(f"<DaysOfOperation>{elements}</DaysOfOperation>")
    nodes = [node]

    assert bank_holidays(None, nodes, region) == expected


@pytest.mark.parametrize("text, expected", [
    ("HALFWAY - FULWOOD", "Halfway – Fulwood"),
    ("Halfway - Fulwood", "Halfway – Fulwood"),
    ("Halfway -Fulwood", "Halfway – Fulwood"),
    ("Halfway- Fulwood", "Halfway – Fulwood"),
    ("Halfway-Fulwood", "Halfway-Fulwood"),
])
def test_format_description(text, expected):
    assert format_description(None, text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Halfway – Fulwood", "Halfway – Fulwood"),
    ("Halfway – Sheffield City Centre – Fulwood", "Halfway – Fulwood"),
    ("Halfway – Sheffield City Centre", "Halfway – Sheffield City Centre"),
    ("Halfway – Sheffield City Centre or Fulwood",
     "Halfway – Sheffield City Centre or Fulwood"),
])
def test_short_description(text, expected):
    assert short_description(None, text, False) == expected


@pytest.mark.parametrize("text, expected", [
    ("Halfway – Fulwood", "Halfway – Fulwood"),
    ("Halfway – Sheffield City Centre – Fulwood", "Halfway – Fulwood"),
    ("Halfway – Sheffield City Centre", "Halfway – Sheffield"),
    ("Halfway – Sheffield City Centre or Fulwood",
     "Halfway – Sheffield Fulwood"),
])
def test_short_description_remove_stop_words(text, expected):
    assert short_description(None, text, True) == expected


@pytest.fixture
def service_codes():
    return ServiceCodes()


@pytest.mark.parametrize("line, description, expected", [
    ("Red Arrow", "Nottingham – Derby", "red-arrow"),
    ("120", "Halfway – Fulwood", "120-halfway-fulwood"),
    ("120A", "Halfway – Fulwood", "120a-halfway-fulwood"),
    ("6.1", "Derby – Belper – Matlock – Bakewell", "6.1-derby-bakewell"),
    ("5", "Inverness – Balloch or Croy", "5-inverness-balloch-croy")
])
def test_service_code(service_codes, line, description, expected):
    assert service_codes.service_code(None, line, description) == expected


def test_service_code_incremenet(service_codes):
    get_code = service_codes.service_code
    line = "120"
    description = "Halfway – Fulwood"
    assert get_code(None, line, description) == "120-halfway-fulwood"
    assert get_code(None, line, description) == "120-halfway-fulwood-2"
    assert get_code(None, line, description) == "120-halfway-fulwood-3"


@pytest.fixture
def row_ids():
    # Set up functions to assign IDs
    return RowIds(check_existing=False)


def always_true(_, *args):
    return True


@pytest.fixture
def xslt():
    with open_binary("nextbus.populate", "tnds.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))
    # Replicate functions which check for existing stops and operators
    xslt_func["stop_exists"] = always_true

    return xslt


def test_transform_tnds(asserts, xslt, row_ids, service_codes):
    output = xslt_transform(et.parse(TNDS_RAW), xslt, region="Y",
                            file="SVRYSBO120A.xml")
    expected = et.parse(TNDS_OUT, parser=et.XMLParser(remove_blank_text=True))

    print(et.tostring(output, pretty_print=True))

    asserts.xml_elements_equal(output.getroot(), expected.getroot())


def test_transform_alt_description(asserts, xslt, row_ids, service_codes):
    data = et.parse(TNDS_RAW)
    ns = {"txc": data.xpath("namespace-uri()")}
    description = data.xpath(
        "/txc:TransXChange/txc:Services/txc:Service/txc:Description",
        namespaces=ns
    )[0]
    # Clear description text, output should be same as origin/destination from
    # standard service will be used instead
    description.text = ""

    output = xslt_transform(et.parse(TNDS_RAW), xslt, region="Y",
                            file="SVRYSBO120A.xml")
    expected = et.parse(TNDS_OUT, parser=et.XMLParser(remove_blank_text=True))

    asserts.xml_elements_equal(output.getroot(), expected.getroot())


def test_transform_tnds_empty(asserts, xslt, row_ids):
    # Set modification to 'delete' - should be excluded
    raw = et.parse(TNDS_RAW)
    raw.getroot().set("Modification", "Delete")
    output = xslt_transform(raw, xslt, region="Y", file="SVRYSBO120.xml")

    asserts.xml_elements_equal(output.getroot(), et.XML("<Data/>"))


def test_transform_tnds_wrong_type(asserts, xslt, row_ids):
    # Set service mode to ferry - should be excluded
    raw = et.parse(TNDS_RAW)
    ns = {"t": raw.xpath("namespace-uri()")}
    raw.xpath("//t:Service/t:Mode", namespaces=ns)[0].text = "ferry"
    output = xslt_transform(raw, xslt, region="Y", file="SVRYSBO120.xml")

    asserts.xml_elements_equal(output.getroot(), et.XML("<Data/>"))


def _as_dict(instance):
    return {k: v for k, v in instance.__dict__.items()
            if k != "_sa_instance_state"}


def test_update_tnds_data(db_loaded, row_ids, service_codes):
    with open_binary("nextbus.populate", "tnds.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))

    # All relevant data already exists for Dagenham Sunday market shuttle;
    # just overwrite route data using a newer file
    file_name = "66-DSM-_-y05-1"
    setup_tnds_functions()
    data = xslt_transform(TNDS_DSM, xslt, region="L", file=file_name)
    populate_database(
        collect_xml_data(data),
        delete=True,
        exclude=(models.Operator, models.LocalOperator)
    )

    assert _as_dict(models.Service.query.one()) == {
        "id": 1,
        "code": "dagenham-sunday-market-shuttle",
        "line": "Dagenham Sunday Market Shuttle",
        "description": "Barking – Dagenham Sunday Market",
        "short_description": "Barking – Dagenham Sunday Market",
        "mode": 1,
        "filename": file_name
    }

    patterns = (
        models.JourneyPattern.query
        .order_by(models.JourneyPattern.id)
        .all()
    )
    assert len(patterns) == 2
    assert _as_dict(patterns[0]) == dict(
        id=1,
        origin="Barking Station",
        destination="Dagenham Sunday Market",
        service_ref=1,
        direction=False,
        date_start=datetime.date(2019, 12, 8),
        date_end=datetime.date(2020, 5, 31),
        local_operator_ref="ATC",
        region_ref="L"
    )

    journeys = (
        models.Journey.query
        .order_by(models.Journey.id)
        .all()
    )
    assert len(journeys) == 26
    assert _as_dict(journeys[0]) == dict(
        id=1,
        pattern_ref=1,
        start_run=None,
        end_run=None,
        departure=datetime.time(8, 30),
        days=0b10000000,
        weeks=None,
        include_holidays=0b0000010001010010,
        exclude_holidays=0b0000001000101000,
        note_code=None,
        note_text=None
    )

    special_days = (
        models.SpecialPeriod.query
        .order_by(models.SpecialPeriod.id)
        .all()
    )
    assert len(special_days) == 26
    assert _as_dict(special_days[0]) == dict(
        id=1,
        journey_ref=1,
        date_start=datetime.date(2020, 5, 8),
        date_end=datetime.date(2020, 5, 8),
        operational=True
    )
