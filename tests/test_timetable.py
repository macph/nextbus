"""
Test timetable generation.
"""
import datetime

import pytest

from nextbus import db, models
from nextbus.timetable import (_query_journeys, _query_timetable, Timetable,
                               TimetableRow, TimetableStop)


SERVICE = 645
DIRECTION = False

GMT = datetime.timezone(datetime.timedelta(hours=0))
BST = datetime.timezone(datetime.timedelta(hours=1))


@pytest.fixture
def load_org(load_db):
    org = models.Organisation(code="TEMP")
    db.session.add(org)
    db.session.commit()

    org_holiday = models.OperatingPeriod(
        id=1,
        org_ref="TEMP",
        date_start=datetime.date(2019, 3, 31),
        date_end=datetime.date(2019, 4, 14),
        working=False
    )
    org_holiday_except = models.ExcludedDate(
        id=1,
        org_ref="TEMP",
        date=datetime.date(2019, 4, 7),
        working=False
    )

    org_working = models.OperatingPeriod(
        id=2,
        org_ref="TEMP",
        date_start=datetime.date(2019, 4, 15),
        date_end=None,
        working=True
    )
    org_working_except = models.ExcludedDate(
        id=2,
        org_ref="TEMP",
        date=datetime.date(2019, 4, 21),
        working=True
    )

    org_0 = models.Organisations(
        org_ref="TEMP",
        journey_ref=400012,
        operational=False,
        working=False
    )
    org_1 = models.Organisations(
        org_ref="TEMP",
        journey_ref=400013,
        operational=True,
        working=False
    )
    org_2 = models.Organisations(
        org_ref="TEMP",
        journey_ref=400014,
        operational=False,
        working=True
    )
    org_3 = models.Organisations(
        org_ref="TEMP",
        journey_ref=400015,
        operational=True,
        working=True
    )
    db.session.add_all([org_holiday, org_holiday_except, org_working,
                        org_working_except, org_0, org_1, org_2, org_3])
    db.session.commit()


@pytest.fixture
def set_night_times(load_db):
    # Remove expiry date for all relevant journey patterns
    (
        models.JourneyPattern.query
        .filter_by(service_ref=SERVICE, direction=DIRECTION)
        .update({"date_end": None})
    )
    # Change all journey times to early morning
    patterns = (db.session.query(models.JourneyPattern.id)
                .filter_by(service_ref=SERVICE, direction=DIRECTION))
    (
        models.Journey.query
        .filter(models.Journey.pattern_ref.in_(patterns))
        .update({
            "departure": models.Journey.departure -
                datetime.timedelta(hours=8, minutes=15)
        }, synchronize_session=False)
    )
    db.session.commit()


def _expected_journeys(first_departure):
    # Journeys for service 645 and outbound direction which are half hourly.
    return [
        (400012 + i, first_departure + i * datetime.timedelta(minutes=30))
        for i in range(13)
    ]


def _set_journeys():
    # Journeys for service 645 and in outbound direction
    return {400012 + i for i in range(13)}


def _set_timezone(tz):
    db.session.execute("SET LOCAL TIME ZONE :tz", {"tz": tz})


def test_journeys_sunday_gmt(load_db):
    # Should be Sunday 3rd March 2019
    date = datetime.date(2019, 3, 3)
    assert date.isoweekday() == 7

    query = _query_journeys(SERVICE, DIRECTION, date).order_by("departure")
    result = query.all()

    assert result == _expected_journeys(
        datetime.datetime(2019, 3, 3, 8, 30, tzinfo=GMT)
    )


def test_journeys_sunday_bst(load_db):
    # Should be Sunday 7th April 2019
    date = datetime.date(2019, 4, 7)
    assert date.isoweekday() == 7

    query = _query_journeys(SERVICE, DIRECTION, date).order_by("departure")
    result = query.all()

    assert result == _expected_journeys(
        datetime.datetime(2019, 4, 7, 8, 30, tzinfo=BST)
    )


def test_journeys_weekday(load_db):
    # Should be Monday 4th March 2019, which this service does not run on
    # except bank holidays
    date = datetime.date(2019, 3, 4)
    assert date.isoweekday() == 1

    result = _query_journeys(SERVICE, DIRECTION, date).all()

    assert not result


def test_journeys_bank_holiday(load_db):
    # Should be 22nd April 2019, ie Easter Monday
    date = datetime.date(2019, 4, 22)
    assert date.isoweekday() == 1

    query = _query_journeys(SERVICE, DIRECTION, date).order_by("departure")
    result = query.all()

    assert result == _expected_journeys(
        datetime.datetime(2019, 4, 22, 8, 30, tzinfo=BST)
    )


def test_journeys_bank_holiday_override(load_db):
    # Override Easter Monday, id 4
    journey = models.Journey.query.get(400012)
    journey.exclude_holidays = 1 << 4
    db.session.commit()

    date = datetime.date(2019, 4, 22)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    assert {r.journey_id for r in result} == _set_journeys() - {400012}


def test_journeys_special_day(load_db):
    # Special period, this journey should run when it didn't before
    special_date = datetime.date(2019, 3, 4)
    sp = models.SpecialPeriod(
        id=1,
        journey_ref=400012,
        date_start=special_date,
        date_end=special_date,
        operational=True
    )
    db.session.add(sp)
    db.session.commit()

    result = _query_journeys(SERVICE, DIRECTION, special_date).all()

    assert {r.journey_id for r in result} == {400012}


def test_journeys_special_day_override_weekday(load_db):
    # Special period, this journey should run when it didn't before
    special_date = datetime.date(2019, 3, 10)
    assert special_date.isoweekday() == 7

    sp = models.SpecialPeriod(
        id=1,
        journey_ref=400012,
        date_start=special_date,
        date_end=special_date,
        operational=False
    )
    db.session.add(sp)
    db.session.commit()

    result = _query_journeys(SERVICE, DIRECTION, special_date).all()

    assert {r.journey_id for r in result} == _set_journeys() - {400012}


def test_journeys_special_day_override_bh(load_db):
    # Special period overriding journey on bank holiday
    special_date = datetime.date(2019, 4, 22)
    sp = models.SpecialPeriod(
        id=1,
        journey_ref=400012,
        date_start=special_date,
        date_end=special_date,
        operational=False
    )
    db.session.add(sp)
    db.session.commit()

    result = _query_journeys(SERVICE, DIRECTION, special_date).all()

    assert {r.journey_id for r in result} == _set_journeys() - {400012}


def test_journeys_organisation_holiday(load_org):
    date = datetime.date(2019, 4, 14)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    # 400012 not operational and 400013 operational during holidays
    assert {r.journey_id for r in result} == _set_journeys() - {400012}


def test_journeys_organisation_holiday_except(load_org):
    date = datetime.date(2019, 4, 7)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    assert {r.journey_id for r in result} == _set_journeys()


def test_journeys_organisation_working(load_org):
    date = datetime.date(2019, 4, 28)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    # 400014 not operational and 400015 operational during working days
    assert {r.journey_id for r in result} == _set_journeys() - {400014}


def test_journeys_organisation_working_except(load_org):
    date = datetime.date(2019, 4, 21)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    assert {r.journey_id for r in result} == _set_journeys()


def test_journeys_organisation_weekday(load_org):
    date = datetime.date(2019, 4, 8)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    # Services associated with organisations still only run on specified days
    assert not result


def test_journeys_organisation_overriden_by_bh(load_org):
    date = datetime.date(2019, 4, 22)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    # Bank holidays and special days override organisation calendars,
    # should run as normal
    assert {r.journey_id for r in result} == _set_journeys()


def test_journeys_in_week_month(load_db):
    # Set first journey to 1st week of month
    models.Journey.query.filter_by(id=400012).update({"weeks": 1 << 0})
    db.session.commit()

    date = datetime.date(2019, 3, 3)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    assert {r.journey_id for r in result} == _set_journeys()


def test_journeys_not_in_week_month(load_db):
    # Set first journey to 2nd week of month
    models.Journey.query.filter_by(id=400012).update({"weeks": 1 << 1})
    db.session.commit()

    date = datetime.date(2019, 3, 3)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    assert {r.journey_id for r in result} == _set_journeys() - {400012}


def test_journeys_bank_holiday_week_month(load_db):
    # Set first journey to 2nd week of month
    models.Journey.query.filter_by(id=400012).update({"weeks": 1 << 1})
    db.session.commit()

    # Bank holiday on 3rd week of month, should still run
    date = datetime.date(2019, 4, 22)
    result = _query_journeys(SERVICE, DIRECTION, date).all()

    assert {r.journey_id for r in result} == _set_journeys()


def test_journeys_no_dst(set_night_times):
    date = datetime.date(2019, 3, 24)
    query = _query_journeys(SERVICE, DIRECTION, date).order_by("departure")
    result = query.all()

    assert result == _expected_journeys(
        datetime.datetime(2019, 3, 24, 0, 15, tzinfo=GMT)
    )


def test_journeys_dst_march(set_night_times):
    # Journeys between 0100-0200 omitted as timezone changes from GMT to BST
    date = datetime.date(2019, 3, 31)
    query = _query_journeys(SERVICE, DIRECTION, date).order_by("departure")

    # Test in different time zones, all queries should return the same results
    _set_timezone("Europe/London")
    result_gb = query.all()
    _set_timezone("UTC")
    result_utc = query.all()

    expected = [
        (400012, datetime.datetime(2019, 3, 31, 0, 15, tzinfo=GMT)),
        (400013, datetime.datetime(2019, 3, 31, 0, 45, tzinfo=GMT)),
        (400016, datetime.datetime(2019, 3, 31, 2, 15, tzinfo=BST)),
        (400017, datetime.datetime(2019, 3, 31, 2, 45, tzinfo=BST)),
        (400018, datetime.datetime(2019, 3, 31, 3, 15, tzinfo=BST)),
        (400019, datetime.datetime(2019, 3, 31, 3, 45, tzinfo=BST)),
        (400020, datetime.datetime(2019, 3, 31, 4, 15, tzinfo=BST)),
        (400021, datetime.datetime(2019, 3, 31, 4, 45, tzinfo=BST)),
        (400022, datetime.datetime(2019, 3, 31, 5, 15, tzinfo=BST)),
        (400023, datetime.datetime(2019, 3, 31, 5, 45, tzinfo=BST)),
        (400024, datetime.datetime(2019, 3, 31, 6, 15, tzinfo=BST))
    ]

    assert result_gb == expected
    assert result_utc == expected


def test_journeys_dst_october(set_night_times):
    # Journeys between 0100-0200 repeated as timezone changes from BST to GMT
    date = datetime.date(2019, 10, 27)
    query = _query_journeys(SERVICE, DIRECTION, date).order_by("departure")

    # Test in different time zones, all queries should return the same results
    _set_timezone("Europe/London")
    result_gb = query.all()
    _set_timezone("UTC")
    result_utc = query.all()

    expected = [
        (400012, datetime.datetime(2019, 10, 27, 0, 15, tzinfo=BST)),
        (400013, datetime.datetime(2019, 10, 27, 0, 45, tzinfo=BST)),
        (400014, datetime.datetime(2019, 10, 27, 1, 15, tzinfo=BST)),
        (400015, datetime.datetime(2019, 10, 27, 1, 45, tzinfo=BST)),
        (400014, datetime.datetime(2019, 10, 27, 1, 15, tzinfo=GMT)),
        (400015, datetime.datetime(2019, 10, 27, 1, 45, tzinfo=GMT)),
        (400016, datetime.datetime(2019, 10, 27, 2, 15, tzinfo=GMT)),
        (400017, datetime.datetime(2019, 10, 27, 2, 45, tzinfo=GMT)),
        (400018, datetime.datetime(2019, 10, 27, 3, 15, tzinfo=GMT)),
        (400019, datetime.datetime(2019, 10, 27, 3, 45, tzinfo=GMT)),
        (400020, datetime.datetime(2019, 10, 27, 4, 15, tzinfo=GMT)),
        (400021, datetime.datetime(2019, 10, 27, 4, 45, tzinfo=GMT)),
        (400022, datetime.datetime(2019, 10, 27, 5, 15, tzinfo=GMT)),
        (400023, datetime.datetime(2019, 10, 27, 5, 45, tzinfo=GMT)),
        (400024, datetime.datetime(2019, 10, 27, 6, 15, tzinfo=GMT))
    ]

    assert result_gb == expected
    assert result_utc == expected


def test_query_timetable_fields(load_db):
    # Should be Sunday 3rd March 2019
    date = datetime.date(2019, 3, 3)
    assert date.isoweekday() == 7

    result = _query_timetable(SERVICE, DIRECTION, date).all()

    assert result[0]._fields == (
        "journey_id",
        "departure",
        "local_operator_code",
        "operator_code",
        "operator_name",
        "note_code",
        "note_text",
        "stop_point_ref",
        "timing_point",
        "utc_arrive",
        "utc_depart",
        "arrive",
        "depart"
    )


def test_query_timetable_sunday(load_db):
    # Should be Sunday 3rd March 2019
    date = datetime.date(2019, 3, 3)
    result = _query_timetable(SERVICE, DIRECTION, date).all()
    assert len(result) == 2 * 13

    first_journey = [r for r in result if r.journey_id == 400012]
    assert first_journey == [
        (400012, datetime.datetime(2019, 3, 3, 8, 30, tzinfo=GMT),
         "ATC", "ATCS", "AT Coaches", None, None, "490000015G", True, None,
         datetime.datetime(2019, 3, 3, 8, 30), None, "0830"),
        (400012, datetime.datetime(2019, 3, 3, 8, 30, tzinfo=GMT),
         "ATC", "ATCS", "AT Coaches", None, None, "490008638S", False,
         datetime.datetime(2019, 3, 3, 8, 34, 35),
         datetime.datetime(2019, 3, 3, 8, 34, 35), "0834", "0834"),
    ]


def test_timetable_empty():
    service, direction, date = 0, False, datetime.date(2019, 3, 3)
    tt = Timetable(service, direction, date, [], {})

    assert not tt
    assert tt.operators == {}
    assert tt.notes == {}
    assert tt.head == []
    assert tt.rows == []


def test_timetable_sunday(load_db):
    date = datetime.date(2019, 3, 3)
    tt = Timetable(SERVICE, DIRECTION, date)

    assert tt.service_id == SERVICE
    assert tt.direction == DIRECTION
    assert tt.date == date
    assert tt.sequence == ["490000015G", "490008638S"]
    assert tt.stops.keys() == {"490000015G", "490008638S"}
    assert tt.operators == {"ATC": "AT Coaches"}
    assert tt.notes == {}
    assert tt.head == [(400012 + i, "ATC", None) for i in range(13)]

    assert [r.stop for r in tt.rows] == ["490000015G", "490008638S"]
    assert [len(r.times) for r in tt.rows] == [13, 13]
    # Test first journey in timetable
    assert [r.times[0] for r in tt.rows] == [
        TimetableStop("490000015G", None, "0830", True, None,
                      datetime.datetime(2019, 3, 3, 8, 30)),
        TimetableStop("490008638S", "0834", "0834", False,
                      datetime.datetime(2019, 3, 3, 8, 34, 35),
                      datetime.datetime(2019, 3, 3, 8, 34, 35))
    ]
