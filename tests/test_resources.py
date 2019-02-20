"""
Tests for views.
"""
import json

import pytest
import sqlalchemy as sa

from nextbus import db, graph, models
from nextbus.resources import _list_geojson


GEOJSON_1 = {
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [0.08238531544, 51.54007091529]
    },
    "properties": {
        "atcoCode": "490000015G",
        "name": "Barking Station",
        "indicator": "G",
        "title": "Barking Station (Stop G)",
        "adminAreaRef": "082",
        "bearing": "SW",
        "stopType": "BCT",
        "locality": "Barking",
        "street": None
    }
}
GEOJSON_2 = {
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [0.09168265891, 51.53148827457]
    },
    "properties": {
        "atcoCode": "490008638N",
        "name": "Greatfields Park",
        "indicator": "N",
        "title": "Greatfields Park (Stop N)",
        "adminAreaRef": "082",
        "bearing": "N",
        "stopType": "BCT",
        "locality": "Barking",
        "street": None
    }
}
GEOJSON_3 = {
    "type": "Feature",
    "geometry": {
        "type": "Point",
        "coordinates": [0.09141512215, 51.53194268342]
    },
    "properties": {
        "atcoCode": "490008638S",
        "name": "Greatfields Park",
        "indicator": "P",
        "title": "Greatfields Park (Stop P)",
        "adminAreaRef": "082",
        "bearing": "S",
        "stopType": "BCT",
        "locality": "Barking",
        "street": None
    }
}


def test_single_stop(load_db):
    stop = (
        db.session.query(models.StopPoint)
        .options(db.joinedload(models.StopPoint.locality))
        .get("490008638S")
    )

    assert stop.to_geojson() == GEOJSON_3


def test_single_stop_no_locality(load_db):
    stop = db.session.query(models.StopPoint).get("490008638S")

    with pytest.raises(sa.exc.InvalidRequestError):
        stop.to_geojson()


def test_multiple_stops(load_db):
    stops = (
        db.session.query(models.StopPoint)
        .options(db.joinedload(models.StopPoint.locality))
        .filter(models.StopPoint.stop_area_ref == "490G00008638")
        .order_by(models.StopPoint.atco_code)
        .all()
    )
    expected = {
        "type": "FeatureCollection",
        "features": [GEOJSON_2, GEOJSON_3]
    }

    assert _list_geojson(stops) == expected


STOP_POINT_JSON = {
    "atcoCode": "490000015G",
    "naptanCode": "53272",
    "title": "Barking Station (Stop G)",
    "name": "Barking Station",
    "indicator": "G",
    "street": None,
    "crossing": None,
    "landmark": None,
    "bearing": "SW",
    "stopType": "BCT",
    "adminAreaRef": "082",
    "latitude": 51.54007091529,
    "longitude": 0.08238531544,
    "adminArea": {
        "code": "082",
        "name": "Greater London",
    },
    "district": {
        "code": "276",
        "name": "Barking and Dagenham",
    },
    "locality": {
        "code": "N0059951",
        "name": "Barking",
    },
    "services": [
        {
            "id": 645,
            "description": "Barking – Dagenham Sunday Market",
            "line": "Dagenham Sunday Market Shuttle",
            "direction": "outbound",
            "reverse": False,
            "origin": "Barking Station",
            "destination": "Dagenham Sunday Market",
            "terminates": False
        },  {
            "id": 645,
            "description": "Barking – Dagenham Sunday Market",
            "line": "Dagenham Sunday Market Shuttle",
            "direction": "inbound",
            "reverse": True,
            "origin": "Dagenham Sunday Market",
            "destination": "Barking Station",
            "terminates": True
        }
    ]
}


def test_full_json(load_db):
    stop = (
        db.session.query(models.StopPoint)
        .options(db.joinedload(models.StopPoint.locality)
                 .joinedload(models.Locality.district),
                 db.joinedload(models.StopPoint.admin_area))
        .order_by(models.JourneyPattern.id)  # consistent order
        .get("490000015G")
    )

    assert stop.to_full_json() == STOP_POINT_JSON


def test_stop_data(client):
    response = client.get("/api/stop/490000015G")

    assert response.status_code == 200
    assert json.loads(response.data) == STOP_POINT_JSON


def test_stop_data_not_found(client):
    response = client.get("/api/stop/490000015F")
    expected = {"message": "Stop point '490000015F' does not exist."}

    assert response.status_code == 404
    assert json.loads(response.data) == expected


SERVICE_JSON = {
    "service": 645,
    "line": "Dagenham Sunday Market Shuttle",
    "description": "Barking – Dagenham Sunday Market",
    "direction": "outbound",
    "reverse": False,
    "mirrored": True,
    "operators": ["AT Coaches"],
    "stops": {
        "490000015G": GEOJSON_1,
        "490008638S": GEOJSON_3
    },
    "sequence": ["490000015G", "490008638S"],
    "paths": {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [[
                [0.08238531544, 51.54007091529],
                [0.09141512215, 51.53194268342]
            ]]
        }
    },
    "layout": [
        ["490000015G", 0, [[0, 0, 0, None]]],
        ["490008638S", 0, []]
    ]
}


def test_service_json(load_db):
    assert graph.service_json(645, False) == SERVICE_JSON


def test_service_api(client):
    response = client.get("/api/route/645/outbound")

    assert response.status_code == 200
    assert json.loads(response.data) == SERVICE_JSON


def test_service_api_not_found(client):
    response = client.get("/api/route/646/outbound")
    expected = {"message": "Service '646' does not exist."}

    assert response.status_code == 404
    assert json.loads(response.data) == expected


def test_live_data_api(client):
    response = client.get("/api/live/490000015G")

    assert response.status_code == 200
    assert response.cache_control.private
    assert response.cache_control.max_age == 60


def test_live_data_api_bad_parameter(client):
    response = client.get("/api/live/")
    expected = {"message": "ATCO code is required."}

    assert response.status_code == 404
    assert json.loads(response.data) == expected


def test_live_data_api_not_found(client):
    response = client.get("/api/live/490000015F")
    expected = {"message": "ATCO code does not exist."}

    assert response.status_code == 404
    assert json.loads(response.data) == expected


def test_stops_tile(client):
    response = client.get("/api/tile/x,y")
    expected = {"message": "API accessed with invalid args: 'x,y'."}

    assert response.status_code == 400
    assert json.loads(response.data) == expected


def test_stops_tile_empty(client):
    response = client.get("/api/tile/0,0")

    assert response.status_code == 200
    assert json.loads(response.data) == {"type": "FeatureCollection",
                                         "features": []}


def test_stops_tile_with_stops(client):
    response = client.get("/api/tile/16392,10892")
    expected_1 = {
        "type": "FeatureCollection",
        "features": [GEOJSON_2, GEOJSON_3]
    }
    expected_2 = {
        "type": "FeatureCollection",
        "features": [GEOJSON_3, GEOJSON_2]
    }

    assert response.status_code == 200
    assert json.loads(response.data) in [expected_1, expected_2]


def test_starred_stops_nothing(client):
    response = client.get("/api/starred/")

    assert response.status_code == 200
    assert json.loads(response.data) == {"stops": []}


def test_starred_stops_add_delete_one(client):
    add = client.post("/api/starred/53272")
    assert add.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": ["53272"]}

    get = client.get("/api/starred/53272")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stop": "53272"}

    delete = client.delete("/api/starred/53272")
    assert delete.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": []}


def test_starred_stops_stop_not_found(client):
    add = client.post("/api/starred/53270")
    expected = {"message": "SMS code '53270' does not exist."}

    assert add.status_code == 404
    assert json.loads(add.data) == expected


def test_starred_stops_post_nothing(client):
    add = client.post("/api/starred/")

    assert add.status_code == 405


def test_starred_stops_delete_nothing(client):
    add = client.delete("/api/starred/")
    expected = {"message": "No cookie has been set."}

    assert add.status_code == 400
    assert json.loads(add.data) == expected


def test_starred_stops_delete_wrong_sms(client):
    add = client.post("/api/starred/53272")
    assert add.status_code == 204

    delete = client.delete("/api/starred/53273")
    expected = {"message": "SMS code '53273' not found within cookie data."}

    assert delete.status_code == 404
    assert json.loads(delete.data) == expected


def test_starred_stops_add_two_stops(client):
    add = client.post("/api/starred/76193")
    assert add.status_code == 204

    add = client.post("/api/starred/76241")
    assert add.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": ["76193", "76241"]}

    get = client.get("/api/starred/76193")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stop": "76193"}


def test_starred_delete_all(client):
    add = client.post("/api/starred/76193")
    assert add.status_code == 204

    add = client.post("/api/starred/76241")
    assert add.status_code == 204

    delete = client.delete("/api/starred/")
    assert delete.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": []}
