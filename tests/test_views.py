"""
Test web app views.
"""
from nextbus import db, models


def test_index_start(client, db_loaded):
    response = client.get("/")

    assert response.status_code == 200
    assert b"You can add your favourite stops here!" in response.data


def test_index_stops_added(client, db_loaded):
    first = client.post("/api/starred/53272")
    assert first.status_code == 204

    second = client.post("/api/starred/76193")
    assert second.status_code == 204

    response = client.get("/")
    assert response.status_code == 200
    assert b"Barking Station" in response.data
    assert b"Greatfields Park" in response.data


def test_about(client):
    response = client.get("/about")

    assert response.status_code == 200
    assert b"This website" in response.data


def _search(client, query):
    return client.post("/search", data={"search": query, "submit": True})


def test_search_query(client, db_loaded):
    response = _search(client, "Road")

    assert response.status_code == 302
    assert "/search/Road" in response.location


def test_search_postcode(client, db_loaded):
    response = _search(client, "IG11 7UG")

    assert response.status_code == 302
    assert "/near/IG11+7UG" in response.location


def test_search_not_postcode(client, db_loaded):
    response = _search(client, "SW1A 0AA")

    assert response.status_code == 302
    assert "/search/SW1A+0AA" in response.location


def test_search_stop_atco(client, db_loaded):
    response = _search(client, "490000015G")

    assert response.status_code == 302
    assert "/stop/atco/490000015G" in response.location


def test_search_stop_sms(client, db_loaded):
    response = _search(client, "53272")

    assert response.status_code == 302
    assert "/stop/atco/490000015G" in response.location


def _search_results(client, query, params=None):
    return client.get("/search/" + query, query_string=params)


def test_search_results(client, db_loaded):
    response = _search_results(client, "Barking")

    assert response.status_code == 200
    assert b"5 results" in response.data


def test_search_results_london(client, db_loaded):
    response = _search_results(client, "Barking", "area=082")

    assert response.status_code == 200
    assert b"5 results" in response.data


def test_search_results_areas(client, db_loaded):
    response = _search_results(client, "Barking", "group=area")

    assert response.status_code == 200
    assert b"1 result" in response.data
    assert (b"<strong>Barking and Dagenham</strong>, Greater London"
            ) in response.data


def test_search_results_places(client, db_loaded):
    response = _search_results(client, "Barking", "group=place")

    assert response.status_code == 200
    assert b"1 result" in response.data
    assert b"<strong>Barking</strong>, Barking and Dagenham" in response.data


def test_search_results_stops(client, db_loaded):
    response = _search_results(client, "Barking", "group=stop")

    assert response.status_code == 200
    assert b"2 results" in response.data
    assert b"Greatfields Park" in response.data
    assert b"Barking Station" in response.data


def test_search_results_services(client, db_loaded):
    response = _search_results(client, "Barking", "group=service")

    assert response.status_code == 200
    assert b"1 result" in response.data
    assert b"Dagenham Sunday Market Shuttle" in response.data
    assert "Barking – Dagenham Sunday Market".encode("UTF-8") in response.data


def test_search_results_repeated(client, db_loaded):
    response = _search_results(client, "Barking", "group=stop&group=service")

    assert response.status_code == 200
    assert b"3 results" in response.data


def test_search_results_both(client, db_loaded):
    response = _search_results(client, "Barking", "area=082&group=stop")

    assert response.status_code == 200
    assert b"2 results" in response.data


def test_search_results_nothing(client, db_loaded):
    response = _search_results(client, "Glasgow")

    assert response.status_code == 200
    assert b"No results found" in response.data
    assert (b"The query <strong>Glasgow</strong> returned no matches"
            ) in response.data


def test_search_results_nothing_filters(client, db_loaded):
    first = _search_results(client, "Greatfields")
    assert first.status_code == 200
    assert b"1 result" in first.data

    second = _search_results(client, "Greatfields", "group=place")

    assert second.status_code == 200
    assert b"No results found" in second.data
    assert (b"No matching results for <strong>Greatfields</strong> with the "
            b"filters you selected") in second.data


def test_search_results_wrong_postcode(client, db_loaded):
    response = _search_results(client, "SW1A+0AA")

    assert response.status_code == 200
    assert (b"The postcode <strong>SW1A 0AA</strong> cannot be found"
            ) in response.data


def test_search_results_invalid_char(client, db_loaded):
    response = _search_results(client, "@")

    assert response.status_code == 200
    assert b"Your query <strong>@</strong> is too short" in response.data


def test_search_results_undefined(client, db_loaded):
    response = _search_results(client, "not+London")

    assert response.status_code == 200
    assert (b"Your query <strong>not London</strong> is too broad"
            ) in response.data


def test_search_results_first_page(client, db_loaded):
    response = _search_results(client, "Barking", "page=1")

    assert response.status_code == 200
    assert b"5 results" in response.data


def test_search_results_out_of_range(client, db_loaded):
    response = _search_results(client, "Barking", "page=2")

    assert response.status_code == 200
    assert b"Page 2 is out of range" in response.data


def test_search_results_invalid_page(client, db_loaded):
    response = _search_results(client, "Barking", "page=none")

    assert response.status_code == 400
    assert b"Your address is not valid" in response.data


def test_search_results_wrong_area(client, db_loaded):
    response = _search_results(client, "Barking", "area=099")

    assert response.status_code == 400
    assert b"Your address is not valid" in response.data


def test_search_results_wrong_group(client, db_loaded):
    response = _search_results(client, "Barking", "group=district")

    assert response.status_code == 400
    assert b"Your address is not valid" in response.data


def test_list_regions(client, db_loaded):
    response = client.get("/list/")

    assert response.status_code == 200
    assert b"L" in response.data
    assert b"GB" not in response.data


def test_region(client, db_loaded):
    response = client.get("/list/region/L")

    assert response.status_code == 200
    assert b"Barking and Dagenham" in response.data


def test_wrong_region(client, db_loaded):
    response = client.get("/list/region/Y")

    assert response.status_code == 404
    assert b"Region with code <strong>Y</strong> does not exist" in response.data


def test_area(client, db_loaded):
    response = client.get("/list/area/082")

    assert response.status_code == 200
    assert b"Barking and Dagenham" in response.data


def test_wrong_area(client, db_loaded):
    response = client.get("/list/area/099")

    assert response.status_code == 404
    assert b"Area with code <strong>099</strong> does not exist" in response.data


def test_district(client, db_loaded):
    response = client.get("/list/district/276")

    assert response.status_code == 200
    assert b"Barking" in response.data


def test_wrong_district(client, db_loaded):
    response = client.get("/list/district/263")

    assert response.status_code == 404
    assert (b"District with code <strong>263</strong> does not exist"
            ) in response.data


def test_locality(client, db_loaded):
    response = client.get("/list/place/N0059951")

    assert response.status_code == 200
    assert b"Group stops" in response.data
    assert b"/stop/atco/490008638S" in response.data
    assert b"/stop/atco/490000015G" in response.data
    assert b"/stop/area" not in response.data
    assert b"/map/" in response.data


def test_locality_grouped(client, db_loaded):
    response = client.get("/list/place/N0059951", query_string="group=true")

    assert response.status_code == 200
    assert b"Ungroup stops" in response.data
    assert b"/stop/area/490G00008638" in response.data
    assert b"/stop/area/490G00015G" in response.data
    assert b"/stop/atco" not in response.data


def test_locality_ungrouped(client, db_loaded):
    first = client.get("/list/place/N0059951")
    second = client.get("/list/place/N0059951", query_string="group=false")

    assert first.data == second.data


def test_locality_redirect(client, db_loaded):
    response = client.get("/list/place/n0059951")

    assert response.status_code == 302
    assert "/list/place/N0059951" in response.location


def test_stop_area(client, db_loaded):
    response = client.get("/stop/area/490G00008638")

    assert response.status_code == 200
    assert b"Greatfields Park" in response.data
    assert b"/stop/atco/490008638S" in response.data
    assert b"Dagenham Sunday Market Shuttle" in response.data
    assert b"/map/" in response.data


def test_wrong_stop_area(client, db_loaded):
    response = client.get("/stop/area/490G00008639")

    assert response.status_code == 404
    assert (b"Stop area <strong>490G00008639</strong> does not exist"
            ) in response.data


def test_stop_atco(client, db_loaded):
    response = client.get("/stop/atco/490008638S")

    assert response.status_code == 200
    assert b"Greatfields Park" in response.data
    assert b"Southbound" in response.data
    assert b"Dagenham Sunday Market Shuttle" in response.data


def test_stop_wrong_atco(client, db_loaded):
    response = client.get("/stop/atco/490008638G")

    assert response.status_code == 404
    assert (b"Stop with ATCO code <strong>490008638G</strong> does not exist"
            ) in response.data


def test_stop_atco_redirect(client, db_loaded):
    response = client.get("/stop/atco/490008638s")

    assert response.status_code == 302
    assert "/stop/atco/490008638S" in response.location


def test_stop_naptan(client, db_loaded):
    response = client.get("/stop/sms/76193")

    assert response.status_code == 200
    assert b"Greatfields Park" in response.data
    assert b"Southbound" in response.data
    assert b"Dagenham Sunday Market Shuttle" in response.data


def test_stop_wrong_naptan(client, db_loaded):
    response = client.get("/stop/sms/50000")

    assert response.status_code == 404
    assert (b"Stop with SMS code <strong>50000</strong> does not exist"
            ) in response.data


def test_query_service(db_loaded):
    service = (
        models.Service.query
        .join(models.Service.patterns)
        .join(models.JourneyPattern.operator)
        .options(db.contains_eager(models.Service.patterns),
                 db.contains_eager(models.Service.operators),
                 db.defaultload(models.Service.operators)
                 .undefer_group("contacts"))
        .filter(models.Service.id == 645)
        .one_or_none()
    )

    assert service.has_mirror(None) == (False, True)
    assert service.has_mirror(False) == (False, True)
    assert service.has_mirror(True) == (True, True)


def test_service(client, db_loaded):
    response = client.get("/service/645/outbound")

    assert response.status_code == 200
    assert b"Outbound" in response.data
    assert b"Inbound" in response.data
    assert b"Barking Station" in response.data
    assert b"Dagenham Sunday Market" in response.data
    assert b"Dagenham Sunday Market Shuttle" in response.data
    assert "Barking – Dagenham Sunday Market".encode("UTF-8") in response.data


def test_service_redirect(client, db_loaded):
    response = client.get("/service/645")

    assert response.status_code == 302
    assert "/service/645/outbound" in response.location


def test_wrong_service(client, db_loaded):
    response = client.get("/service/655")

    assert response.status_code == 404
    assert b"Service <strong>655</strong> does not exist" in response.data


def test_service_wrong_direction(client, db_loaded):
    response = client.get("/service/645/neither")

    assert response.status_code == 404


def test_service_timetable(client, db_loaded):
    response = client.get("/service/645/outbound/timetable")

    assert response.status_code == 200


def test_service_timetable_redirect(client, db_loaded):
    response = client.get("/service/645/timetable")

    assert response.status_code == 302
    assert "/service/645/outbound/timetable" in response.location


def test_postcode(client, db_loaded):
    response = client.get("/near/IG11+7UG")

    assert response.status_code == 200
    assert b"Postcode IG11 7UG, Barking and Dagenham" in response.data
    assert b"/stop/atco/490008638N" in response.data
    assert b"/stop/atco/490008638S" in response.data


def test_postcode_redirect(client, db_loaded):
    response = client.get("/near/ig117ug")

    assert response.status_code == 302
    assert "/near/IG11+7UG" in response.location


def test_wrong_postcode(client, db_loaded):
    response = client.get("/near/SW1A+0AA")

    assert response.status_code == 404
    assert b"Postcode <strong>SW1A 0AA</strong> does not exist" in response.data


def test_location(client, db_loaded):
    response = client.get("/near/51.531299,0.092135")

    assert response.status_code == 200
    assert b"/stop/atco/490008638N" in response.data
    assert b"/stop/atco/490008638S" in response.data


def test_location_away(client, db_loaded):
    response = client.get("/near/51.436333,-4.837392")

    assert response.status_code == 200
    assert b"No stops found within 500 metres" in response.data


def test_location_oob(client, db_loaded):
    response = client.get("/near/54,-10")

    assert response.status_code == 404
    assert (b"Latitude and longitude coordinates are too far from Great Britain"
            ) in response.data
