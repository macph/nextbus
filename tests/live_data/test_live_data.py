"""
Testing live retrieval of data; will use sample data in the same format.
"""
import os
import json

from flask import current_app
import pytest
import requests

from definitions import ROOT_DIR
from nextbus import tapi


ATCO_CODE = "490013767D"
TEST_DIR = os.path.dirname(os.path.realpath(__file__))


@pytest.fixture
def api_data():
    return {
        "atcocode": "490000015G",
        "smscode": "53272",
        "request_time": "2019-06-02T08:25:45Z",
        "name": "Barking Station (Stop G)",
        "stop_name": "Barking Station",
        "bearing": "SW",
        "indicator": "Stop G",
        "locality": "Barking, Barking and Dagenham",
        "departures": {
            "all": [{
                "mode": "bus",
                "line": "Barking Dagenham Sunday Market Shuttle",
                "line_name": "Barking Dagenham Sunday Market Shuttle",
                "direction": "Dagenham Sunday Market, Dagenham",
                "operator": "ATC",
                "date": "2019-06-02",
                "expected_departure_date": "2019-06-02",
                "aimed_departure_time": "09:30",
                "expected_departure_time": "09:30",
                "best_departure_estimate": "09:30",
                "source": "Countdown instant",
                "dir": "outbound",
                "operator_name": "AT Coaches"
            }, {
                "mode": "bus",
                "line": "Barking Dagenham Sunday Market Shuttle",
                "line_name": "Barking Dagenham Sunday Market Shuttle",
                "direction": "Dagenham Sunday Market, Dagenham",
                "operator": "ATC",
                "date": "2019-06-02",
                "expected_departure_date": None,
                "aimed_departure_time": "10:00",
                "expected_departure_time": None,
                "best_departure_estimate": "10:00",
                "source": "Countdown instant",
                "dir": "outbound",
                "operator_name": "AT Coaches"
            }]
        }
    }


def test_live_stop_live(api_data):
    live_data = tapi.LiveData(api_data)
    assert live_data.datetime.isoformat() == "2019-06-02T08:25:45+00:00"
    assert live_data.atco_code == "490000015G"
    assert live_data.naptan_code == "53272"

    assert len(live_data.services) == 1
    assert len(live_data.services[0]) == 2

    first = live_data.services[0][0]
    assert first.line == "Barking Dagenham Sunday Market Shuttle"
    assert first.name == "Barking Dagenham Sunday Market Shuttle"
    assert first.destination == "Dagenham Sunday Market"
    assert first.operator == "ATC"
    assert first.operator_name == "AT Coaches"
    assert first.is_live
    assert first.expected == "2019-06-02T09:30:00+01:00"
    assert first.seconds == 255


def test_live_json(api_data):
    expected = {
        "atcoCode": "490000015G",
        "smsCode": "53272",
        "isoDate": "2019-06-02T08:25:45+00:00",
        "localTime": "09:25",
        "services": [{
            "line": "Barking Dagenham Sunday Market Shuttle",
            "name": "Barking Dagenham Sunday Market Shuttle",
            "dest": "Dagenham Sunday Market",
            "opName": "AT Coaches",
            "opCode": "ATC",
            "expected": [{
                "live": True,
                "secs": 255,
                "expDate": "2019-06-02T09:30:00+01:00"
            }, {
                "live": False,
                "secs": 2055,
                "expDate": "2019-06-02T10:00:00+01:00"
            }]
        }]
    }
    assert tapi.LiveData(api_data).to_json() == expected
    # Switch around services - should still output same order
    api_data["departures"]["all"] = api_data["departures"]["all"][::-1]
    assert tapi.LiveData(api_data).to_json() == expected


def test_live_json_threshold(api_data):
    assert tapi.LiveData(api_data).to_json(max_minutes=1) == {
        "atcoCode": "490000015G",
        "smsCode": "53272",
        "isoDate": "2019-06-02T08:25:45+00:00",
        "localTime": "09:25",
        "services": []
    }


def test_live_json_out_of_date(api_data):
    api_data.update({
        "request_time": "2019-06-02T09:25:45Z"
    })
    assert tapi.LiveData(api_data).to_json() == {
        "atcoCode": "490000015G",
        "smsCode": "53272",
        "isoDate": "2019-06-02T09:25:45+00:00",
        "localTime": "10:25",
        "services": []
    }


def test_live_stop_ambiguous(api_data):
    # Last Sunday of October, at 00:50 UTC (01:50 local time)
    api_data.update({
        "request_time": "2019-10-27T00:50:45Z",
    })
    # Don't need 2nd service
    del api_data["departures"]["all"][1]
    # Next service is at 01:30 local time - in the repeated 1st hour
    api_data["departures"]["all"][0].update({
        "date": "2019-10-27",
        "expected_departure_date": "2019-10-27",
        "aimed_departure_time": "01:30",
        "expected_departure_time": "01:30",
        "best_departure_estimate": "01:30",
    })
    live_data = tapi.LiveData(api_data)
    assert live_data.datetime.isoformat() == "2019-10-27T00:50:45+00:00"

    service = live_data.services[0][0]
    assert service.is_live
    assert service.expected == "2019-10-27T01:30:00+00:00"
    assert service.seconds == 2355
    assert tapi.LiveData(api_data).to_json() == {
        "atcoCode": "490000015G",
        "smsCode": "53272",
        "isoDate": "2019-10-27T00:50:45+00:00",
        "localTime": "01:50",
        "services": [{
            "line": "Barking Dagenham Sunday Market Shuttle",
            "name": "Barking Dagenham Sunday Market Shuttle",
            "dest": "Dagenham Sunday Market",
            "opName": "AT Coaches",
            "opCode": "ATC",
            "expected": [{
                "live": True,
                "secs": 2355,
                "expDate": "2019-10-27T01:30:00+00:00"
            }]
        }]
    }


class Mocker:
    def __init__(self, func):
        self.func = func
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))

        return self.func(*args, **kwargs)


@pytest.fixture
def mock_response(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"name": "A bus stop"}

    monkeypatch.setattr(requests, "Response", Response)

    return Response


@pytest.fixture
def mock_request(monkeypatch, mock_response):
    @Mocker
    def get(*args, **kwargs):
        return mock_response()

    monkeypatch.setattr(requests, "get", get)

    return get


def test_sample_data_ungrouped(with_app, mock_request):
    current_app.config["TRANSPORT_API_ACTIVE"] = False
    sample_data = tapi.get_live_data("", group=False)

    with open(os.path.join(ROOT_DIR, "samples/tapi_live.json")) as f:
        assert sample_data == json.load(f)


def test_sample_data_grouped(with_app, mock_request):
    current_app.config["TRANSPORT_API_ACTIVE"] = False
    sample_data = tapi.get_live_data("", group=True)

    with open(os.path.join(ROOT_DIR, "samples/tapi_live_group.json")) as f:
        assert sample_data == json.load(f)


def test_live_data_data(with_app, mock_request):
    current_app.config["TRANSPORT_API_ACTIVE"] = True
    new_data = tapi.get_live_data(ATCO_CODE)

    assert new_data == {"name": "A bus stop"}


def test_live_data_arguments_default(with_app, mock_request):
    current_app.config["TRANSPORT_API_ACTIVE"] = True
    tapi.get_live_data(ATCO_CODE)

    parameters = {
        "group": "yes",
        "nextbuses": "yes",
        "limit": 6
    }
    assert mock_request.calls == [
        ((tapi.URL_FCC % ATCO_CODE,), {"params": parameters})
    ]


def test_live_data_arguments_ungrouped(with_app, mock_request):
    current_app.config["TRANSPORT_API_ACTIVE"] = True
    tapi.get_live_data(ATCO_CODE, group=False, limit=8)

    parameters = {
        "group": "no",
        "nextbuses": "yes",
        "limit": 8
    }
    assert mock_request.calls == [
        ((tapi.URL_FCC % ATCO_CODE,), {"params": parameters})
    ]


def test_live_data_arguments_api_key(with_app, mock_request):
    api_id, api_key = "some_api_id", "some_api_key"
    current_app.config.update({
        "TRANSPORT_API_ACTIVE": True,
        "TRANSPORT_API_ID": api_id,
        "TRANSPORT_API_KEY": api_key
    })
    tapi.get_live_data(ATCO_CODE)

    parameters = {
        "group": "yes",
        "nextbuses": "yes",
        "limit": 6,
        "app_id": api_id,
        "app_key": api_key
    }
    assert mock_request.calls == [
        ((tapi.URL_API % ATCO_CODE,), {"params": parameters})
    ]


def test_live_json_value_error(with_app, mock_response, mock_request):
    def _raise_error(*args, **kwargs):
        raise ValueError

    mock_response.json = _raise_error

    with pytest.raises(ValueError, match="Data is expected to be"):
        current_app.config["TRANSPORT_API_ACTIVE"] = True
        tapi.get_live_data(ATCO_CODE)


def test_live_data_error(with_app, mock_response, mock_request):
    def _error_response(*args, **kwargs):
        return {"error": "This is a mock error."}

    mock_response.json = _error_response

    message = "Error with data: This is a mock error."
    with pytest.raises(ValueError, match=message):
        current_app.config["TRANSPORT_API_ACTIVE"] = True
        tapi.get_live_data(ATCO_CODE)


def test_live_data_default(with_app, mock_response, mock_request):
    with open(os.path.join(TEST_DIR, "tapi_data.json")) as data:
        raw_data = json.load(data)

    def _return_data(*args, **kwargs):
        return raw_data
    mock_response.json = _return_data

    with open(os.path.join(TEST_DIR, "tapi_processed.json")) as data:
        processed_data = json.load(data)

    current_app.config["TRANSPORT_API_ACTIVE"] = True
    assert tapi.get_nextbus_times(ATCO_CODE) == processed_data
