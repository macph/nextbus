import collections
import datetime
import json

import requests

from nextbus import models
from nextbus.populate import utils


BANK_HOLIDAY_URL = r"https://www.gov.uk/bank-holidays.json"
HOLIDAYS = [
    {"holiday_id": 1, "name": "new year’s day", "region": None, "note": None},
    {"holiday_id": 2, "name": "2nd january", "region": "scotland", "note": None},
    {"holiday_id": 3, "name": "good friday", "region": None, "note": None},
    {"holiday_id": 4, "name": "easter monday", "region": None, "note": None},
    {"holiday_id": 5, "name": "early may bank holiday", "region": None, "note": None},
    {"holiday_id": 6, "name": "spring bank holiday", "region": None, "note": None},
    {"holiday_id": 7, "name": "summer bank holiday", "region": "england-and-wales", "note": None},
    {"holiday_id": 8, "name": "summer bank holiday", "region": "scotland", "note": None},
    {"holiday_id": 9, "name": "christmas day", "region": None, "note": None},
    {"holiday_id": 10, "name": "boxing day", "region": None, "note": None},
    {"holiday_id": 11, "name": "christmas day", "region": None, "note": "substitute day"},
    {"holiday_id": 12, "name": "boxing day", "region": None, "note": "substitute day"},
    {"holiday_id": 13, "name": "new year’s day", "region": None, "note": "substitute day"},
]


HolidayDate = collections.namedtuple("HolidayDate", ("id", "date"))


def _get_holiday_dates(data):
    try:
        divisions = data.values()
    except AttributeError:
        raise ValueError("The given data is not an object")

    holiday_dates = set()
    for division in divisions:
        region = _get_property(division, "division")
        events = _get_property(division, "events")
        for event in events:
            holiday_date = _get_holiday(region, event)
            if holiday_date is not None:
                holiday_dates.add(holiday_date)

    years = set()
    for bh in holiday_dates:
        years.add(bh.date.year)

    for year in years:
        # The API provides bank holidays that will have been substituted if the
        # occasion (eg New Year's Day) fell on a weekend. Bus timetables will
        # require both dates so they will need to be infilled as well.
        holiday_dates.add(HolidayDate(1, datetime.date(year, 1, 1)))
        holiday_dates.add(HolidayDate(14, datetime.date(year, 12, 24)))
        holiday_dates.add(HolidayDate(9, datetime.date(year, 12, 25)))
        holiday_dates.add(HolidayDate(10, datetime.date(year, 12, 26)))
        holiday_dates.add(HolidayDate(15, datetime.date(year, 12, 31)))

    return holiday_dates


def _get_holiday(region, event):
    title = _get_property(event, "title").lower()
    notes = _get_property(event, "notes").lower()

    # Match the substitute days first so check in reverse order
    for match in reversed(HOLIDAYS):
        if (
            match["name"] in title and
            (match["region"] is None or match["region"] == region) and
            (match["note"] is None or match["note"] in notes)
        ):
            break
    else:
        # No matches found
        return None

    date = _get_property(event, "date")
    try:
        dt = datetime.datetime.strptime(date, "%Y-%m-%d")
    except (ValueError, TypeError) as e:
        raise ValueError(
            f"Invalid date for bank holiday {event['title']}"
        ) from e

    return HolidayDate(match["holiday_id"], dt.date())


def _get_property(obj, name):
    try:
        return obj[name]
    except TypeError as e:
        raise ValueError(f"Expected an object") from e
    except KeyError as e:
        raise ValueError(f"Expected {name!r} property in object") from e


def populate_holiday_data(connection, path=None):
    """ Retrieve and convert bank holiday data from the GOV.UK API and load them
        into the database.
        :param connection: Database connection for population.
        :param path: Path to JSON file. If this is None it will be downloaded.
    """
    if path is not None:
        utils.logger.info(f"Opening JSON file at {path!r}")
        with open(path, "r") as f:
            data = json.load(f)
    else:
        utils.logger.info(f"Downloading JSON data from {BANK_HOLIDAY_URL!r}")
        data = requests.get(BANK_HOLIDAY_URL).json()

    try:
        holiday_dates = _get_holiday_dates(data)
    except ValueError as e:
        # Log error and exit; leave any existing bank holiday data alone
        utils.logger.error(f"Failed to transform bank holiday data", exc_info=e)
        return

    # Convert the holiday date data to rows and insert them
    rows = []
    for holiday_date in holiday_dates:
        rows.append({
            "holiday_ref": holiday_date.id,
            "date": holiday_date.date,
        })

    table = models.BankHolidayDate.__table__
    connection.execute(table.delete())
    connection.execute(table.insert().values(rows))
    utils.logger.info("Bank holiday date population done")
