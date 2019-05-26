"""
Interacts with Transport API to retrieve live bus times data.
"""
import json
import os

import dateutil.parser
import dateutil.tz
import requests
from flask import current_app

from definitions import ROOT_DIR


GB_TZ = dateutil.tz.gettz("Europe/London")
UTC = dateutil.tz.UTC

URL_API = r"https://transportapi.com/v3/uk/bus/stop/%s/live.json"
URL_FCC = r"http://fcc.transportapi.com/v3/uk/bus/stop/%s/live.json"


def get_live_data(atco_code, nextbuses=True, group=True, limit=6):
    """ Retrieves data from the NextBuses API via Transport API. If
        TRANSPORT_API_ACTIVE is not True, sample data from a file will be
        loaded instead for testing.

        :param atco_code: The ATCO code for the bus/tram stop.
        :param nextbuses: Use the NextBuses API to get live bus times. If
        false, the timetabled information is retrieved instead.
        :param group: Group services by their number, instead of having a time-
        ordered list.
        :param limit: Number of services to retrieve for each service number
        (or all if not grouping).
        :returns: a Python dict converted from JSON.
    """
    if current_app.config.get("TRANSPORT_API_ACTIVE"):
        parameters = {
            "group": "yes" if group else "no",
            "nextbuses": "yes" if nextbuses else "no",
            "limit": limit
        }
        app_id = current_app.config.get("TRANSPORT_API_ID")
        app_key = current_app.config.get("TRANSPORT_API_KEY")
        if app_id and app_key:
            # Use the Transport API with app ID and key
            parameters["app_id"] = app_id
            parameters["app_key"] = app_key
            url = URL_API
        else:
            # Use the FCC (Future Capault Cities) API instead, intended for
            # experimentation
            url = URL_FCC

        current_app.logger.debug("Requesting live data for ATCO code %s"
                                 % atco_code)
        req = requests.get(url % atco_code, params=parameters)
        req.raise_for_status()
        try:
            data = req.json()
        except ValueError as err:
            raise ValueError("Data is expected to be in JSON format.") from err
        if data.get("error") is not None:
            raise ValueError("Error with data: " + data["error"])
        current_app.logger.debug("Data received:\n" + repr(data))

    else:
        if group:
            file_name = "samples/tapi_live_group.json"
        else:
            file_name = "samples/tapi_live.json"
        with open(os.path.join(ROOT_DIR, file_name), "r") as sample_file:
            data = json.load(sample_file)
        current_app.logger.debug("Received sample data from file '%s'" %
                                 file_name)

    return data


class Departure:
    """ Holds data for each journey expected at a stop, with line, operator and
        times.

        :param data: Data for a departure.
        :param dt_requested: Date time API call was requested at.
    """
    __slots__ = ("line", "name", "destination", "operator", "operator_name",
                 "is_live", "expected", "datetime")

    def __init__(self, data, dt_requested):
        self.line = data["line"]
        self.name = data["line_name"]
        # Ignore all text after comma or opening parenthesis
        self.destination = data["direction"].split(",")[0].split("(")[0]
        self.operator = data["operator"]
        self.operator_name = data["operator_name"]

        live = (data["expected_departure_date"],
                data["expected_departure_time"])
        tt = (data["date"], data["aimed_departure_time"])

        self.is_live = None not in live
        if self.is_live:
            dt = dateutil.parser.parse("T".join(live)).replace(tzinfo=GB_TZ)
        elif None not in tt:
            dt = dateutil.parser.parse("T".join(tt)).replace(tzinfo=GB_TZ)
        else:
            dt = None

        self.expected = (dt - dt_requested).seconds if dt is not None else None
        self.datetime = dt.isoformat() if dt is not None else None

    def __repr__(self):
        return "<Departure(%r, %r, %r)>" % (
            self.line, self.operator, self.datetime
        )


def _get_expected(journey):
    return journey.expected


def _first_expected(journeys):
    return journeys[0].expected


class LiveData:
    """ Parses live service data.

        :param data: Data passed from API.
    """
    __slots__ = ("atco_code", "naptan_code", "datetime", "services")

    def __init__(self, data):
        self.atco_code = data["atcocode"]
        self.naptan_code = data["smscode"]
        self.datetime = dateutil.parser.parse(data["request_time"])
        if self.datetime.tzinfo is None:
            # Assume naive datetime is UTC
            self.datetime = self.datetime.replace(tzinfo=UTC)

        self.services = self._group_journeys(data)

    def __repr__(self):
        return "<LiveData(%r, %r)>" % (self.atco_code, self.datetime)

    def _group_journeys(self, data):
        """ Group journeys by line, operator and destination and sorted by
            departure time.
        """
        groups = {}
        for departures in data["departures"].values():
            for data in departures:
                journey = Departure(data, self.datetime)
                key = journey.line, journey.operator, journey.destination
                if journey.expected is not None:
                    groups.setdefault(key, []).append(journey)

        for service in groups.values():
            service.sort(key=_get_expected)

        return sorted(groups.values(), key=_first_expected)

    def to_json(self, max_minutes=60):
        """ Serializes live data for stop as JSON.

            :param max_minutes: Include only journeys expected to come before
            this limit. If zero all journeys will be included.
        """
        services = []
        for service in self.services:
            first = service[0]
            times = []
            for j in service:
                if max_minutes > 0 and j.expected > max_minutes * 60:
                    continue
                times.append({
                    "live": j.is_live,
                    "secs": j.expected,
                    "expDate": j.datetime
                })
            if not times:
                continue

            services.append({
                "line": first.line,
                "name": first.name,
                "dest": first.destination,
                "opName": first.operator_name,
                "opCode": first.operator,
                "expected": times
            })

        return {
            "atcoCode": self.atco_code,
            "naptanCode": self.naptan_code,
            "isoDate": self.datetime.isoformat(),
            "localTime": self.datetime.astimezone(GB_TZ).strftime("%H:%M"),
            "services": services
        }


def get_nextbus_times(atco_code, **kwargs):
    """ Parses the received live bus times, grouping each service/destination
        for a more readable layout.

        :param atco_code: ATCO code for the bus/tram stop.
        :param kwargs: All keyword arguments to be passed to
        get_live_data(). By default 'group' is True and 'limit' is 6.
        :returns: JSON serializable dict with required lists and info.
    """
    params = kwargs.copy()
    params["group"] = params.get("group", True)
    params["limit"] = params.get("limit", 6)
    data = get_live_data(atco_code, **params)
    new_data = LiveData(data).to_json()

    current_app.logger.debug("%d services for ATCO code %s:\n%r" %
                             (len(new_data["services"]), atco_code, new_data))

    return new_data
