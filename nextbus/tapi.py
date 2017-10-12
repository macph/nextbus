"""
Interacts with Transport API to retrieve live bus times data.
"""
import json
import requests
from nextbus import app


def _get_nextbus_times(atco_code, nextbuses=True, strip_key=True):
    """ Retrieves data from the NextBuses API via Transport API.

        :param atco_code: The ATCO code for the bus/tram stop.
        :param nextbuses: Use the NextBuses API to get live bus times. If
        false, the timetabled information is retrieved instead.
        :param strip_key: If true: remove all parameters from URLs in the JSON
        data. Necessary if passing the data directly to the client as Transport
        API includes the id/key as parameters to link to their route timetable.
        :returns: a Python dict converted from JSON.
    """
    url_live_json = r'https://transportapi.com/v3/uk/bus/stop/%s/live.json'
    parameters = {
        'group': 'no',
        'nextbuses': 'yes' if nextbuses else 'no',
        'limit': 30,
        'app_id': app.config.get('TRANSPORT_API_ID'),
        'app_key': app.config.get('TRANSPORT_API_KEY')
    }
    req = requests.get(url_live_json % atco_code, params=parameters)
    req.raise_for_status()
    if 'application/json' not in req.headers['Content-Type']:
        raise ValueError('Data should be in JSON format; '
                         + req.headers["Content-Type"])
    data = req.json()
    if data.get('error') is not None:
        raise ValueError('Error with data: ' + data["error"])
    if strip_key:
        for key, value in data['departures'].items():
            for service in value:
                if service.get('id'):
                    service['id'] = service['id'].rsplit('?')[0]

    return data


import os.path
from definitions import ROOT_DIR


USE_API = False


def get_nextbus_times(atco_code):
    """ Placeholder function for testing, to avoid hitting the API while
        testing.
    """
    if USE_API:
        data = _get_nextbus_times(atco_code)
    else:
        with open(os.path.join(ROOT_DIR, 'samples/tapi_live.json'), 'r') as jf:
            data = json.load(jf)

    return data
