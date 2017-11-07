"""
Interacts with Transport API to retrieve live bus times data.
"""
import datetime
import os
import json
import dateutil.parser
import pytz
import requests
from flask import current_app
from definitions import ROOT_DIR


CUT_OFF_MIN = 60


def _get_nextbus_times(atco_code, nextbuses=True, strip_key=True, group=False,
                       limit=30):
    """ Retrieves data from the NextBuses API via Transport API.

        :param atco_code: The ATCO code for the bus/tram stop.
        :param nextbuses: Use the NextBuses API to get live bus times. If
        false, the timetabled information is retrieved instead.
        :param strip_key: If true: remove all parameters from URLs in the JSON
        data. Necessary if passing the data directly to the client as Transport
        API includes the id/key as parameters to link to their route timetable.
        :param group: Group services by their number, instead of having a time-
        ordered list.
        :param limit: Number of services to retrieve for each service number
        (or all if not grouping).
        :returns: a Python dict converted from JSON.
    """
    url_live_json = r'https://transportapi.com/v3/uk/bus/stop/%s/live.json'
    parameters = {
        'group': 'yes' if group else 'no',
        'nextbuses': 'yes' if nextbuses else 'no',
        'limit': limit,
        'app_id': current_app.config.get('TRANSPORT_API_ID'),
        'app_key': current_app.config.get('TRANSPORT_API_KEY')
    }
    req = requests.get(url_live_json % atco_code, params=parameters)
    req.raise_for_status()
    if 'application/json' not in req.headers['Content-Type']:
        raise ValueError('Data should be in JSON format; ' + req.headers["Content-Type"])
    data = req.json()
    if data.get('error') is not None:
        raise ValueError('Error with data: ' + data["error"])
    if strip_key:
        for key, value in data['departures'].items():
            for service in value:
                if service.get('id'):
                    service['id'] = service['id'].rsplit('?')[0]

    return data


def get_nextbus_times(atco_code, group=False, **kwargs):
    """ Placeholder function for testing, to avoid hitting the API. """
    if current_app.config.get('TRANSPORT_API_ACTIVE', False):
        data = _get_nextbus_times(atco_code, group=group, **kwargs)
    else:
        file_name = "samples/tapi_live_group.json" if group else "samples/tapi_live.json"
        with open(os.path.join(ROOT_DIR, file_name), 'r') as jf:
            data = json.load(jf)

    return data


def parse_nextbus_times(atco_code, **kwargs):
    """ Parses the receieved live bus times, grouping each service/destination
        for a more readable layout.

        :param atco_code: ATCO code for the bus/tram stop.
        :param kwargs: All keyword arguments to be passed to
        get_nextbus_times(). By default 'group' is True and 'limit' is 6.
        :returns: JSON serializable dict with required lists and info.
    """
    utc, gb = pytz.utc, pytz.timezone('Europe/London')
    list_services = []

    data = get_nextbus_times(atco_code, group=True, limit=6, **kwargs)
    req_date = dateutil.parser.parse(data['request_time'])
    if req_date.tzinfo is None:
        # Assume naive datetime is UTC
        req_date = utc.localize(req_date)

    for line, services in data['departures'].items():
        for sv in services:
            arr_date = sv['expected_departure_date']
            arr_time = sv['expected_departure_time']
            is_live = arr_date is not None and arr_time is not None
            if not is_live:
                arr_date = sv['date']
                arr_time = sv['aimed_departure_time']

            arr_date_time = arr_date + 'T' + arr_time
            native_exp_date = datetime.datetime.strptime(arr_date_time, r"%Y-%m-%dT%H:%M")
            exp_date = gb.localize(native_exp_date)
            exp_sec = (exp_date - req_date).seconds
            exp_min = round(exp_sec / 60)
            if CUT_OFF_MIN and exp_min > CUT_OFF_MIN:
                # Don't need services any further out than 60 minutes
                continue
            str_min = "due" if exp_min < 2 else "%d min" % exp_min

            new_dest = sv['direction'].split(',')[0].split('(')[0]
            sv_expected = {
                'live': is_live,
                'due': str_min,
                'sec': exp_sec,
                'iso_date': exp_date.isoformat(),
                'local_time': exp_date.strftime("%H:%M")
            }

            for nsv in list_services:
                if line == nsv['line'] and new_dest == nsv['dest']:
                    nsv['expected'].append(sv_expected)
                    break
            else:
                new_service = {
                    'line': line,
                    'name': sv['line_name'],
                    'dest': new_dest,
                    'operator': sv['operator_name'],
                    'code': sv['operator'],
                    'expected': [sv_expected]
                }
                list_services.append(new_service)

    for sg in list_services:
        sg['expected'] = sorted(sg['expected'], key=lambda sv: sv['sec'])
    list_services.sort(key=lambda sg: sg['expected'][0]['sec'])

    local_time = req_date.astimezone(gb)
    new_data = {
        'atco_code': data['atcocode'],
        'naptan_code': data['smscode'],
        'iso_date': req_date.isoformat(),
        'local_time': local_time.strftime("%H:%M:%S"),
        'services': list_services
    }

    return new_data
