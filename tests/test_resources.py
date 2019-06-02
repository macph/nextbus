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
        "smsCode": "53272",
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
        "smsCode": "76241",
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
        "smsCode": "76193",
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


def test_single_stop(db_loaded):
    stop = (
        db.session.query(models.StopPoint)
        .options(db.joinedload(models.StopPoint.locality))
        .get("490008638S")
    )

    assert stop.to_geojson() == GEOJSON_3


def test_single_stop_no_locality(db_loaded):
    stop = db.session.query(models.StopPoint).get("490008638S")

    with pytest.raises(sa.exc.InvalidRequestError):
        stop.to_geojson()


def test_multiple_stops(db_loaded):
    stops = (
        db.session.query(models.StopPoint)
        .options(db.joinedload(models.StopPoint.locality))
        .filter(models.StopPoint.stop_area_ref == "490G00008638")
        .order_by(models.StopPoint.atco_code)
        .all()
    )

    assert _list_geojson(stops) == {
        "type": "FeatureCollection",
        "features": [GEOJSON_2, GEOJSON_3]
    }


STOP_POINT_JSON = {
    "atcoCode": "490000015G",
    "smsCode": "53272",
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
    "active": True,
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
            "terminates": False,
            "operatorCodes": ["ATC"]
        }, {
            "id": 645,
            "description": "Barking – Dagenham Sunday Market",
            "line": "Dagenham Sunday Market Shuttle",
            "direction": "inbound",
            "reverse": True,
            "origin": "Dagenham Sunday Market",
            "destination": "Barking Station",
            "terminates": True,
            "operatorCodes": ["ATC"]
        }
    ],
    "operators": [{
        "code": "ATC",
        "name": "AT Coaches"
    }]
}


def test_full_json(db_loaded):
    stop = (
        db.session.query(models.StopPoint)
        .options(db.joinedload(models.StopPoint.locality)
                 .joinedload(models.Locality.district),
                 db.joinedload(models.StopPoint.admin_area))
        .order_by(models.JourneyPattern.id)  # consistent order
        .get("490000015G")
    )

    assert stop.to_full_json() == STOP_POINT_JSON


def test_stop_data(client, db_loaded):
    response = client.get("/api/stop/490000015G")

    assert response.status_code == 200
    assert json.loads(response.data) == STOP_POINT_JSON


def test_stop_data_not_found(client, db_loaded):
    response = client.get("/api/stop/490000015F")

    assert response.status_code == 404
    assert json.loads(response.data) == {
        "message": "Stop point '490000015F' does not exist."
    }


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


def test_service_json(db_loaded):
    assert graph.service_json(645, False) == SERVICE_JSON


def test_api_bad_parameter(client, db_loaded):
    response = client.get("/api/dummy/")

    assert response.status_code == 404
    assert json.loads(response.data) == {
        "message": "API endpoint '/api/dummy/' does not exist."
    }


def test_service_api(client, db_loaded):
    response = client.get("/api/route/645/outbound")

    assert response.status_code == 200
    assert json.loads(response.data) == SERVICE_JSON


def test_service_api_not_found(client, db_loaded):
    response = client.get("/api/route/646/outbound")

    assert response.status_code == 404
    assert json.loads(response.data) == {
        "message": "Service '646' does not exist."
    }


def test_live_data_api(client, db_loaded):
    response = client.get("/api/live/490000015G")

    assert response.status_code == 200
    assert response.cache_control.private
    assert response.cache_control.max_age == 60


def test_live_data_api_not_found(client, db_loaded):
    response = client.get("/api/live/490000015F")

    assert response.status_code == 404
    assert json.loads(response.data) == {
        "message": "ATCO code '490000015F' does not exist."
    }


def test_stops_tile(client, db_loaded):
    response = client.get("/api/tile/x,y")

    assert response.status_code == 400
    assert json.loads(response.data) == {
        "message": "API accessed with invalid args: 'x,y'."
    }


def test_stops_tile_empty(client, db_loaded):
    response = client.get("/api/tile/0,0")

    assert response.status_code == 200
    assert json.loads(response.data) == {"type": "FeatureCollection",
                                         "features": []}


def test_stops_tile_with_stops(client, db_loaded):
    response = client.get("/api/tile/16392,10892")
    data = json.loads(response.data)

    assert response.status_code == 200
    assert set(data.keys()) == {"type", "features"}
    assert data["type"] == "FeatureCollection"
    assert data["features"] in [[GEOJSON_2, GEOJSON_3], [GEOJSON_3, GEOJSON_2]]


def test_starred_stops_get_nothing(client, db_loaded):
    response = client.get("/api/starred/")

    assert response.status_code == 200
    assert json.loads(response.data) == {"stops": None}


def test_starred_stops_get_stop(client, db_loaded):
    get = client.get("/api/starred/53272")

    assert get.status_code == 405


def test_starred_stops_add_twice(client, db_loaded):
    add = client.post("/api/starred/53272")
    assert add.status_code == 201

    add = client.post("/api/starred/53272")
    assert add.status_code == 422
    assert json.loads(add.data) == {
        "message": "SMS code '53272' already in list of starred stops."
    }


def test_starred_stops_add_delete_one(client, db_loaded):
    add = client.post("/api/starred/53272")
    assert add.status_code == 201

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": ["53272"]}

    delete = client.delete("/api/starred/53272")
    assert delete.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": []}


def test_starred_stops_stop_not_found(client, db_loaded):
    add = client.post("/api/starred/53270")

    assert add.status_code == 404
    assert json.loads(add.data) == {
        "message": "SMS code '53270' does not exist."
    }


def test_starred_stops_post_nothing(client, db_loaded):
    add = client.post("/api/starred/")

    assert add.status_code == 405


def test_starred_stops_delete_nothing(client, db_loaded):
    add = client.delete("/api/starred/")

    assert add.status_code == 422
    assert json.loads(add.data) == {"message": "No cookie has been set."}


def test_starred_stops_delete_wrong_sms(client, db_loaded):
    add = client.post("/api/starred/53272")
    assert add.status_code == 201

    delete = client.delete("/api/starred/53273")

    assert delete.status_code == 404
    assert json.loads(delete.data) == {
        "message": "SMS code '53273' not in list of starred stops."
    }


def test_starred_stops_add_two_stops(client, db_loaded):
    add = client.post("/api/starred/76193")
    assert add.status_code == 201

    add = client.post("/api/starred/76241")
    assert add.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": ["76193", "76241"]}


def test_starred_delete_all(client, db_loaded):
    client.post("/api/starred/76193")
    client.post("/api/starred/76241")

    delete = client.delete("/api/starred/")
    assert delete.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": None}


def test_starred_swap(client, db_loaded):
    client.post("/api/starred/53272")
    client.post("/api/starred/76193")
    client.post("/api/starred/76241")

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": ["53272", "76193", "76241"]}

    patch = client.patch("/api/starred/53272/2")
    assert patch.status_code == 204

    get = client.get("/api/starred/")
    assert get.status_code == 200
    assert json.loads(get.data) == {"stops": ["76193", "76241", "53272"]}


def test_starred_no_index(client, db_loaded):
    client.post("/api/starred/76193")
    client.post("/api/starred/76241")

    patch = client.patch("/api/starred/76193")
    assert patch.status_code == 405


def test_starred_not_in_list(client, db_loaded):
    client.post("/api/starred/76193")
    client.post("/api/starred/76241")

    patch = client.patch("/api/starred/53272/2")
    assert patch.status_code == 404
    assert json.loads(patch.data) == {
        "message": "Stop '53272' not in list of starred stops."
    }


def test_starred_out_of_range(client, db_loaded):
    client.post("/api/starred/76193")
    client.post("/api/starred/76241")

    patch = client.patch("/api/starred/76241/5")
    assert patch.status_code == 400
    assert json.loads(patch.data) == {
        "message": "Index 5 is outside range [0, 1]."
    }


def test_starred_stops_data_nothing(client, db_loaded):
    response = client.get("/api/starred/data")

    assert response.status_code == 200
    assert json.loads(response.data) == {
        "type": "FeatureCollection",
        "features": []
    }


def test_starred_stops_data_list(client, db_loaded):
    client.post("/api/starred/76241")
    client.post("/api/starred/76193")

    response = client.get("/api/starred/data")

    assert response.status_code == 200
    assert json.loads(response.data) == {
        "type": "FeatureCollection",
        "features": [GEOJSON_2, GEOJSON_3]
    }
