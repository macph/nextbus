"""
Testing live retrieval of data; will use sample data in the same format.
"""
import copy
import datetime
import os
import json

from flask import current_app
import pytest
import requests

from definitions import ROOT_DIR
from nextbus import create_app, tapi


ATCO_CODE = "490013767D"
TEST_DIR = os.path.dirname(os.path.realpath(__file__))


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
