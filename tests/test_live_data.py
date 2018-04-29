"""
Testing live retrieval of data; will use sample data in the same format.
"""
import copy
import datetime
import os
import json
import unittest
from unittest import mock

from flask import current_app

from definitions import ROOT_DIR
from nextbus import create_app, tapi
from nextbus.tapi import _Services


TEST_DIR = os.path.dirname(os.path.realpath(__file__))


class BaseRequestsTests(unittest.TestCase):
    """ Base class to test functions using the requests package.
    """
    def setUp(self):
        # Create a mock object to simulate requests.Response, returned from
        # a patched requests.get() function
        self.mock_response = mock.Mock("requests.Response")
        # A successful request results in Response.raise_for_status() doing
        # nothing
        self.mock_response.raise_for_status = lambda: None
        # Response.json() returns JSON data as a Python list or dict
        self.mock_response.json = lambda: {"name": "A bus stop"}
        # When used in context, any requests.get() functions are patched and
        # return the above mock request.Response object
        self.mock_request = mock.patch("requests.get",
                                       return_value=self.mock_response)

    def tearDown(self):
        del self.mock_response
        del self.mock_request


class TAPITests(BaseRequestsTests):
    """ Testing retrieval of live data from API with the `get_live_data`
        function.
    """
    atco_code = "490013767D"

    def setUp(self):
        self.app = create_app(config_obj="default_config.DevelopmentConfig")
        super(TAPITests, self).setUp()

    def tearDown(self):
        del self.app
        super(TAPITests, self).tearDown()

    def test_sample_data_ungrouped(self):
        with self.app.app_context():
            current_app.config["TRANSPORT_API_ACTIVE"] = False
            sample_data = tapi.get_live_data("", group=False)

        with open(os.path.join(ROOT_DIR, "samples/tapi_live.json")) as f:
            self.assertEqual(sample_data, json.load(f))

    def test_sample_data_grouped(self):
        with self.app.app_context():
            current_app.config["TRANSPORT_API_ACTIVE"] = False
            sample_data = tapi.get_live_data("", group=True)

        with open(os.path.join(ROOT_DIR, "samples/tapi_live_group.json")) as f:
            self.assertEqual(sample_data, json.load(f))

    def test_live_data_data(self):
        with self.app.app_context(), self.mock_request:
            current_app.config["TRANSPORT_API_ACTIVE"] = True
            new_data = tapi.get_live_data("490013767D")
            self.assertEqual(new_data, {"name": "A bus stop"})

    def test_live_data_arguments_default(self):
        parameters = {
            "group": "yes",
            "nextbuses": "yes",
            "limit": 6
        }
        with self.app.app_context(), self.mock_request as req:
            current_app.config["TRANSPORT_API_ACTIVE"] = True
            tapi.get_live_data(self.atco_code)
            req.assert_called_once_with(tapi.URL_FCC % self.atco_code,
                                        params=parameters)

    def test_live_data_arguments_ungrouped(self):
        parameters = {
            "group": "no",
            "nextbuses": "yes",
            "limit": 8
        }
        with self.app.app_context(), self.mock_request as req:
            current_app.config["TRANSPORT_API_ACTIVE"] = True
            tapi.get_live_data(self.atco_code, group=False, limit=8)
            req.assert_called_once_with(tapi.URL_FCC % self.atco_code,
                                        params=parameters)

    def test_live_data_arguments_api_key(self):
        api_id, api_key = "some_api_id", "some_api_key"
        parameters = {
            "group": "yes",
            "nextbuses": "yes",
            "limit": 6,
            "app_id": api_id,
            "app_key": api_key
        }
        with self.app.app_context(), self.mock_request as req:
            current_app.config.update({
                "TRANSPORT_API_ACTIVE": True,
                "TRANSPORT_API_ID": api_id,
                "TRANSPORT_API_KEY": api_key
            })
            tapi.get_live_data(self.atco_code)
            req.assert_called_once_with(tapi.URL_API % self.atco_code,
                                        params=parameters)

    def test_live_json_value_error(self):
        def _raise_error():
            raise ValueError
        self.mock_response.json = _raise_error

        with self.app.app_context(), self.mock_request,\
                self.assertRaisesRegex(ValueError, "Data is expected to be"):
            current_app.config["TRANSPORT_API_ACTIVE"] = True
            tapi.get_live_data(self.atco_code)

    def test_live_data_error(self):
        self.mock_response.json = lambda: {"error": "This is a mock error."}

        with self.app.app_context(), self.mock_request,\
                self.assertRaisesRegex(ValueError, "Error with data: This is "
                                       "a mock error."):
            current_app.config["TRANSPORT_API_ACTIVE"] = True
            tapi.get_live_data(self.atco_code)


class LiveServiceTests(unittest.TestCase):
    """ Testing the ``_Services`` class which parses each service and groups
        them.
    """
    maxDiff = None
    req_date = datetime.datetime(2018, 2, 3, 9, 25, 35,
                                 tzinfo=datetime.timezone.utc)
    service_24 = {
        "mode": "bus",
        "line": "24",
        "line_name": "24",
        "direction": "Pimlico",
        "operator": "ML",
        "date": "2018-02-03",
        "expected_departure_date": "2018-02-03",
        "aimed_departure_time": "09:35",
        "expected_departure_time": "09:34",
        "best_departure_estimate": "09:34",
        "source": "Countdown instant",
        "dir": "inbound",
        "operator_name": "METROLINE TRAVEL LIMITED"
    }
    expected_24 = {
        "line": "24",
        "name": "24",
        "dest": "Pimlico",
        "op_name": "METROLINE TRAVEL LIMITED",
        "op_code": "ML",
        "expected": [{
                "live": True,
                "secs": 505,
                "exp_date": "2018-02-03T09:34:00+00:00"
        }]
    }
    service_29 = {
        "mode": "bus",
        "line": "29",
        "line_name": "29",
        "direction": "Trafalgar Sq",
        "operator": "TFL",
        "date": "2018-02-03",
        "expected_departure_date": "2018-02-03",
        "aimed_departure_time": None,
        "expected_departure_time": "09:30",
        "best_departure_estimate": "09:30",
        "source": "Countdown instant",
        "dir": None,
        "operator_name": None
    }
    expected_29 = {
        "line": "29",
        "name": "29",
        "dest": "Trafalgar Sq",
        "op_name": None,
        "op_code": "TFL",
        "expected": [{
                "live": True,
                "secs": 265,
                "exp_date": "2018-02-03T09:30:00+00:00"
        }]
    }

    def setUp(self):
        self.sv = _Services(self.req_date)

    def tearDown(self):
        del self.sv

    def test_one_service(self):
        self.sv.add("24", self.service_24)
        self.assertEqual(self.sv.list, [self.expected_24])

    def test_two_services(self):
        self.sv.add("24", self.service_24)
        self.sv.add("29", self.service_29)
        self.assertEqual(self.sv.list,
                         [self.expected_24, self.expected_29])

    def test_order_two_services(self):
        self.sv.add("24", self.service_24)
        self.sv.add("29", self.service_29)
        self.assertEqual(self.sv.ordered_list(),
                         [self.expected_29, self.expected_24])

    def test_order_three_services(self):
        self.sv.add("24", self.service_24)
        self.sv.add("29", self.service_29)

        # Add another service with time changed
        new_service = self.service_24.copy()
        new_service["aimed_departure_time"] = "09:27"
        new_service["expected_departure_time"] = "09:29"
        new_service["best_departure_estimate"] = "09:29"
        self.sv.add("24", new_service)

        # Need to modify nested dict, use deep copy
        new_expected_24 = copy.deepcopy(self.expected_24)
        # Earlier service, so prepend with insert at position zero
        new_expected_24["expected"].insert(0, {
            "live": True,
            "secs": 205,
            "exp_date": "2018-02-03T09:29:00+00:00"
        })
        self.assertEqual(self.sv.ordered_list(),
                         [new_expected_24, self.expected_29])


class LiveDataTests(BaseRequestsTests):
    """ Testing the `get_nextbus_times` function for parsing of data from the
        Transport API.
    """
    maxDiff = None
    atco_code = "490013767D"

    def setUp(self):
        self.app = create_app(config_obj="default_config.DevelopmentConfig")
        super(LiveDataTests, self).setUp()

    def tearDown(self):
        del self.app
        super(LiveDataTests, self).tearDown()

    def test_live_data_default(self):
        with open(os.path.join(TEST_DIR, "tapi_data.json")) as data:
            raw_data = json.load(data)
            self.mock_response.json = lambda: raw_data

        with open(os.path.join(TEST_DIR, "tapi_processed.json")) as data:
            processed_data = json.load(data)

        with self.app.app_context(), self.mock_request:
            self.app.config["TRANSPORT_API_ACTIVE"] = True
            new_data = tapi.get_nextbus_times(self.atco_code)
            self.assertEqual(processed_data, new_data)
