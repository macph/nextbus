"""
Interacts with Transport API to retrieve live bus times data.
"""
import os
import json

import dateutil.parser
import pytz
import requests
from flask import current_app

from definitions import ROOT_DIR


GB_TZ = pytz.timezone("Europe/London")
UTC = pytz.utc

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

        req = requests.get(url % atco_code, params=parameters)
        req.raise_for_status()
        try:
            data = req.json()
        except ValueError as err:
            raise ValueError("Data is expected to be in JSON format.") from err
        if data.get("error") is not None:
            raise ValueError("Error with data: " + data["error"])
        current_app.logger.info("Received live data for ATCO code %s"
                                % atco_code)
        current_app.logger.debug("Data received:\n" + repr(data))

    else:
        if group:
            file_name = "samples/tapi_live_group.json"
        else:
            file_name = "samples/tapi_live.json"
        with open(os.path.join(ROOT_DIR, file_name), "r") as sample_file:
            data = json.load(sample_file)
        current_app.logger.info("Received sample data from file '%s'"
                                %  file_name)

    return data


class _Services(object):
    """ Helper class for parsing live service data.

        :param request_date: Datetime object for when the live data was
        requested.
    """
    CUT_OFF_MIN = 60

    def __init__(self, request_date):
        self.req_date = request_date
        self.list = []

    def add(self, line, service):
        """ Adds service to list of services, or to a line/destination if it
            already exists.

            :param line: String for bus or tram route label, used for grouping
            services
            :param service: Dictionary object for each service.
        """
        exp_dt = (service["date"], service["aimed_departure_time"])
        live_dt = (service["expected_departure_date"],
                   service["expected_departure_time"])

        if all(d is not None for d in exp_dt):
            exp_date = GB_TZ.localize(dateutil.parser.parse("T".join(exp_dt)))
        else:
            exp_date = None

        is_live = all(d is not None for d in live_dt)
        if is_live:
            live_date = GB_TZ.localize(
                dateutil.parser.parse("T".join(live_dt))
            )
            exp_sec = (live_date - self.req_date).seconds
        elif exp_date is not None:
            live_date = None
            exp_sec = (exp_date - self.req_date).seconds
        else:
            # Record has no live or timetabled times? Skip over
            return

        if self.CUT_OFF_MIN and exp_sec > self.CUT_OFF_MIN * 60:
            # Don't need services any further out than 60 minutes
            return

        # Ignore all text after comma or opening parenthesis
        new_dest = service["direction"].split(",")[0].split("(")[0]
        sv_expected = {
            "live": is_live,
            "secs": exp_sec,
            "exp_date": live_date.isoformat() if live_date is not None else
                        exp_date.isoformat()
        }

        for new_sv in self.list:
            if line == new_sv["line"] and new_dest == new_sv["dest"]:
                new_sv["expected"].append(sv_expected)
                break
        else:
            # No matching line and/or destination, create a new group
            new_service = {
                "line": line,
                "name": service["line_name"],
                "dest": new_dest,
                "op_name": service["operator_name"],
                "op_code": service["operator"],
                "expected": [sv_expected]
            }
            self.list.append(new_service)

    def ordered_list(self):
        """ Returns a list of lines, sorted by first service expected. """
        for group in self.list:
            group["expected"].sort(key=lambda sv: sv["secs"])
        self.list.sort(key=lambda sg: sg["expected"][0]["secs"])

        return self.list


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

    req_date = dateutil.parser.parse(data["request_time"])
    if req_date.tzinfo is None:
        # Assume naive datetime is UTC
        req_date = UTC.localize(req_date)

    services = _Services(req_date)
    for line, group in data["departures"].items():
        for sv in group:
            try:
                services.add(line, sv)
            except:
                current_app.logger.error("Error with request for stop %s. "
                                         "Data from request:\n%r" % data)
                raise

    new_data = {
        "atco_code": data["atcocode"],
        "naptan_code": data["smscode"],
        "iso_date": req_date.isoformat(),
        "local_time": req_date.astimezone(GB_TZ).strftime("%H:%M"),
        "services": services.ordered_list()
    }
    current_app.logger.debug(
        "%d services for ATCO code %s:\n%r"
        % (len(new_data["services"]), atco_code, repr(new_data))
    )

    return new_data
