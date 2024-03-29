"""
Interacts with Transport API to retrieve live bus times data.
"""
import dateutil.parser
import dateutil.tz
import requests
from flask import current_app

GB_TZ = dateutil.tz.gettz("Europe/London")

URL_API = r"https://transportapi.com/v3/uk/bus/stop/{code}/live.json"
URL_FCC = r"http://fcc.transportapi.com/v3/uk/bus/stop/{code}/live.json"


def get_live_data(atco_code, nextbuses=True, group=True, limit=6):
    """ Retrieves data from the NextBuses API via Transport API. If
        TRANSPORT_API_ACTIVE is not True, sample data from a file will be
        loaded instead for testing.

        :param atco_code: The ATCO code for the bus/tram stop.
        :param nextbuses: Use the NextBuses API to get live bus times outside
        the TfL area.
        :param group: Group services by their number, instead of having a time-
        ordered list.
        :param limit: Number of services to retrieve for each service number
        (or all if not grouping).
        :returns: a Python dict converted from JSON.
    """
    if not current_app.config.get("TRANSPORT_API_ACTIVE"):
        raise ValueError("TRANSPORT_API_ACTIVE not set to True")

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
        # Use the FCC (Future Catapult Cities) API instead, intended for
        # experimentation
        url = URL_FCC

    current_app.logger.debug(
        f"Requesting live data for ATCO code {atco_code}"
    )
    response = requests.get(url.format(code=atco_code), params=parameters)
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError as err:
        raise ValueError("Data is expected to be in JSON format.") from err
    if data.get("error") is not None:
        raise ValueError("Error with data: " + data["error"])
    current_app.logger.debug(f"Data received: {response.reason!r}")

    return data


class Departure:
    """ Holds data for each journey expected at a stop, with line, operator and
        times.
    """
    __slots__ = ("line", "name", "destination", "operator", "operator_name",
                 "is_live", "expected", "seconds")

    def __init__(self, line, name, destination, operator, operator_name,
                 is_live, expected, seconds):
        self.line = line
        self.name = name
        self.destination = destination
        self.operator = operator
        self.operator_name = operator_name
        self.is_live = is_live
        self.expected = expected
        self.seconds = seconds

    @classmethod
    def from_data(cls, data, dt_requested):
        line = data["line"]
        name = data["line_name"]
        # Ignore all text after comma or opening parenthesis
        destination = data["direction"].split(",")[0].split("(")[0]
        operator = data["operator"]
        operator_name = data["operator_name"]

        live = (data["expected_departure_date"],
                data["expected_departure_time"])
        tt = (data["date"], data["aimed_departure_time"])

        is_live = all(i is not None for i in live)
        is_tt = all(i is not None for i in tt)
        if is_live or is_tt:
            dt_string = "T".join(live if is_live else tt)
            dt = dateutil.parser.parse(dt_string).replace(tzinfo=GB_TZ)
        else:
            dt = None

        if dt is not None:
            difference = dt - dt_requested
            # If datetime is ambiguous (eg BST -> GMT on last Sunday of October)
            # assume times before request time are in the next hour
            if difference.days < 0 and dateutil.tz.datetime_ambiguous(dt):
                dt = dt.replace(fold=1)
                difference = dt - dt_requested
            expected = dt.isoformat()
            seconds = difference.total_seconds()
        else:
            expected = None
            seconds = None

        return cls(line, name, destination, operator, operator_name, is_live,
                   expected, seconds)

    def __repr__(self):
        return (
            f"<Departure({self.line!r}, {self.operator!r}, {self.expected!r})>"
        )


def _seconds(journey):
    return journey.seconds


def _first_expected(journeys):
    return journeys[0].seconds


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
            self.datetime = self.datetime.replace(tzinfo=dateutil.tz.UTC)

        self.services = self._group_journeys(data)

    def __repr__(self):
        return f"<LiveData({self.atco_code!r}, {self.datetime!r})>"

    def _group_journeys(self, data):
        """ Group journeys by line, operator and destination and sorted by
            departure time.
        """
        groups = {}
        for departures in data["departures"].values():
            for data in departures:
                journey = Departure.from_data(data, self.datetime)
                key = journey.line, journey.operator, journey.destination
                if journey.seconds is not None and journey.seconds >= 0:
                    groups.setdefault(key, []).append(journey)

        for service in groups.values():
            service.sort(key=_seconds)

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
                if not max_minutes or j.seconds <= max_minutes * 60:
                    times.append({
                        "live": j.is_live,
                        "secs": j.seconds,
                        "expDate": j.expected
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
            "live": True,
            "smsCode": self.naptan_code,
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

    current_app.logger.debug(
        f"{len(new_data['services'])} services for ATCO code {atco_code!r}:\n"
        f"{new_data!r}"
    )

    return new_data
