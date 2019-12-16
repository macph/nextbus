import datetime


TEST_DATA = {
    "region": [
        {"code": "GB", "name": "Great Britain"},
        {"code": "L", "name": "Greater London"}
    ],
    "admin_area": [
        {
            "code": "082",
            "name": "Greater London",
            "atco_code": "490",
            "region_ref": "L"
        }
    ],
    "district": [
        {
            "code": "276",
            "name": "Barking and Dagenham",
            "admin_area_ref": "082"
        }
    ],
    "locality": [
        {
            "code": "N0059951",
            "name": "Barking",
            "easting": 544250,
            "northing": 183970,
            "longitude": 0.07844558,
            "latitude": 51.53621,
            "admin_area_ref": "082",
            "district_ref": "276",
            "parent_ref": "N0060403"
        }
    ],
    "stop_area": [
        {
            "code": "490G00008638",
            "name": "Greatfields Park",
            "stop_area_type": "GPBS",
            "active": True,
            "easting": 545173,
            "northing": 183499,
            "longitude": 0.09155012684,
            "latitude": 51.53174243533,
            "admin_area_ref": "082",
            "locality_ref": "N0059951"
        },
        {
            "code": "490G00015G",
            "name": "Barking Station",
            "stop_area_type": "GCLS",
            "active": True,
            "easting": 544446,
            "northing": 184347,
            "longitude": 0.0814241115,
            "latitude": 51.53954841056,
            "admin_area_ref": "082",
            "locality_ref": "N0059951"
        }
    ],
    "stop_point": [
        {
            "atco_code": "490008638N",
            "naptan_code": "76241",
            "landmark": None,
            "street": None,
            "crossing": None,
            "indicator": "Stop N",
            "short_ind": "N",
            "easting": 545183,
            "northing": 183471,
            "longitude": 0.09168265891,
            "latitude": 51.53148827457,
            "stop_type": "BCT",
            "active": True,
            "bearing": "N",
            "name": "Greatfields Park",
            "admin_area_ref": "082",
            "locality_ref": "N0059951",
            "stop_area_ref": "490G00008638"
        },
        {
            "atco_code": "490008638S",
            "naptan_code": "76193",
            "landmark": None,
            "street": None,
            "crossing": None,
            "indicator": "Stop P",
            "short_ind": "P",
            "easting": 545163,
            "northing": 183521,
            "longitude": 0.09141512215,
            "latitude": 51.53194268342,
            "stop_type": "BCT",
            "active": True,
            "bearing": "S",
            "name": "Greatfields Park",
            "admin_area_ref": "082",
            "locality_ref": "N0059951",
            "stop_area_ref": "490G00008638"
        },
        {
            "atco_code": "490000015G",
            "naptan_code": "53272",
            "landmark": None,
            "street": None,
            "crossing": None,
            "indicator": "Stop G",
            "short_ind": "G",
            "easting": 544511,
            "northing": 184407,
            "longitude": 0.08238531544,
            "latitude": 51.54007091529,
            "stop_type": "BCT",
            "active": True,
            "bearing": "SW",
            "name": "Barking Station",
            "admin_area_ref": "082",
            "locality_ref": "N0059951",
            "stop_area_ref": "490G00015G"
        },
        {
            "atco_code": "490000015H",
            "naptan_code": "72621",
            "landmark": None,
            "street": None,
            "crossing": None,
            "indicator": "Stop H",
            "short_ind": "H",
            "easting": 544443,
            "northing": 184312,
            "longitude": 0.08136653435,
            "latitude": 51.53923468629,
            "stop_type": "BCT",
            "active": True,
            "bearing": "SW",
            "name": "Barking Station",
            "admin_area_ref": "082",
            "locality_ref": "N0059951",
            "stop_area_ref": "490G00015G"
        },
        {
            "atco_code": "490000015K",
            "naptan_code": "47665",
            "landmark": None,
            "street": None,
            "crossing": None,
            "indicator": "Stop K",
            "short_ind": "K",
            "easting": 544433,
            "northing": 184322,
            "longitude": 0.0812265438,
            "latitude": 51.53932709757,
            "stop_type": "BCT",
            "active": True,
            "bearing": "NE",
            "name": "Barking Station",
            "admin_area_ref": "082",
            "locality_ref": "N0059951",
            "stop_area_ref": "490G00015G"
        },
        {
            "atco_code": "490000015L",
            "naptan_code": "50989",
            "landmark": None,
            "street": None,
            "crossing": None,
            "indicator": "Stop L",
            "short_ind": "L",
            "easting": 544489,
            "northing": 184395,
            "longitude": 0.08206338972,
            "latitude": 51.5399687169,
            "stop_type": "BCT",
            "active": True,
            "bearing": "NE",
            "name": "Barking Station",
            "admin_area_ref": "082",
            "locality_ref": "N0059951",
            "stop_area_ref": "490G00015G"
        },
        {
            "atco_code": "490000015N",
            "naptan_code": "91335",
            "landmark": None,
            "street": None,
            "crossing": None,
            "indicator": "Stop N",
            "short_ind": "N",
            "easting": 544446,
            "northing": 184313,
            "longitude": 0.0814101714,
            "latitude": 51.53924290473,
            "stop_type": "BCT",
            "active": True,
            "bearing": "SW",
            "name": "Barking Station",
            "admin_area_ref": "082",
            "locality_ref": "N0059951",
            "stop_area_ref": "490G00015G"
        }
    ],
    "postcode": [
        {
            "index": "IG117UG",
            "text": "IG11 7UG",
            "easting": 545215,
            "northing": 183451,
            "longitude": 0.092135,
            "latitude": 51.531299,
            "admin_area_ref": "082",
            "district_ref": "276"
        },
        {
            "index": "IG117UQ",
            "text": "IG11 7UQ",
            "easting": 545163,
            "northing": 183552,
            "longitude": 0.091455,
            "latitude": 51.532221,
            "admin_area_ref": "082",
            "district_ref": "276"
        },
        {
            "index": "IG118RY",
            "text": "IG11 8RY",
            "easting": 544523,
            "northing": 184409,
            "longitude": 0.082559,
            "latitude": 51.540084,
            "admin_area_ref": "082",
            "district_ref": "276"
        }
    ],
    "operator": [
        {
            "code": "ATCS",
            "name": "AT Coaches",
            "region_ref": "L",
            "mode": 1,
        }
    ],
    "local_operator": [
        {
            "code": "ATC",
            "region_ref": "L",
            "operator_ref": "ATCS",
            "name": "AT Coaches"
        }
    ],
    "service": [
        {
            "id": 645,
            "code": "dagenham-sunday-market-shuttle",
            "line": "Dagenham Sunday Market Shuttle",
            "description": "Barking – Dagenham Sunday Market",
            "short_description": "Barking – Dagenham Sunday Market",
            "mode": 1,
            "filename": "66-DSM-_-y05-1"
        }
    ],
    "journey_pattern": [
        {
            "id": 110732,
            "origin": "Barking Station",
            "destination": "Dagenham Sunday Market",
            "service_ref": 645,
            "direction": False,
            "date_start": datetime.date(2019, 2, 10),
            "date_end": datetime.date(2019, 8, 4),
            "local_operator_ref": "ATC",
            "region_ref": "L"
        },
        {
            "id": 110733,
            "origin": "Dagenham Sunday Market",
            "destination": "Barking Station",
            "service_ref": 645,
            "direction": True,
            "date_start": datetime.date(2019, 2, 10),
            "date_end": datetime.date(2019, 8, 4),
            "local_operator_ref": "ATC",
            "region_ref": "L"
        }
    ],
    "journey_link": [
        {
            "id": 4398955,
            "pattern_ref": 110732,
            "stop_point_ref": "490000015G",
            "run_time": None,
            "wait_arrive": None,
            "wait_leave": datetime.timedelta(0),
            "timing_point": True,
            "principal_point": True,
            "stopping": True,
            "sequence": 1
        },
        {
            "id": 4398956,
            "pattern_ref": 110732,
            "stop_point_ref": "490008638S",
            "run_time": datetime.timedelta(minutes=4, seconds=35),
            "wait_arrive": datetime.timedelta(0),
            "wait_leave": datetime.timedelta(0),
            "timing_point": False,
            "principal_point": True,
            "stopping": True,
            "sequence": 2
        },
        {
            "id": 4398957,
            "pattern_ref": 110732,
            "stop_point_ref": None,
            "run_time": datetime.timedelta(minutes=10, seconds=25),
            "wait_arrive": datetime.timedelta(0),
            "wait_leave": None,
            "timing_point": True,
            "principal_point": True,
            "stopping": True,
            "sequence": 3
        },
        {
            "id": 4398958,
            "pattern_ref": 110733,
            "stop_point_ref": None,
            "run_time": None,
            "wait_arrive": None,
            "wait_leave": datetime.timedelta(0),
            "timing_point": True,
            "principal_point": True,
            "stopping": True,
            "sequence": 1
        },
        {
            "id": 4398959,
            "pattern_ref": 110733,
            "stop_point_ref": "490008638N",
            "run_time": datetime.timedelta(minutes=9, seconds=8),
            "wait_arrive": datetime.timedelta(0),
            "wait_leave": datetime.timedelta(0),
            "timing_point": False,
            "principal_point": True,
            "stopping": True,
            "sequence": 2
        },
        {
            "id": 4398960,
            "pattern_ref": 110733,
            "stop_point_ref": "490000015G",
            "run_time": datetime.timedelta(minutes=5, seconds=52),
            "wait_arrive": datetime.timedelta(0),
            "wait_leave": None,
            "timing_point": True,
            "principal_point": True,
            "stopping": True,
            "sequence": 3
        }
    ],
    "journey": [
        {
            "id": 400012,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(8, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400013,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(9, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400014,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(9, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400015,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(10, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400016,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(10, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400017,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(11, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400018,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(11, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400019,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(12, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400020,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(12, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400021,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(13, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400022,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(13, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400023,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(14, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400024,
            "pattern_ref": 110732,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(14, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400025,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(9, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400026,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(9, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400027,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(10, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400028,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(10, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400029,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(11, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400030,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(11, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400031,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(12, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400032,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(12, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400033,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(13, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400034,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(13, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400035,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(14, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400036,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(14, 30, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        },
        {
            "id": 400037,
            "pattern_ref": 110733,
            "start_run": None,
            "end_run": None,
            "departure": datetime.time(15, 0, 0),
            "days": 128,
            "weeks": None,
            "include_holidays": 112,
            "exclude_holidays": 0,
            "note_code": None,
            "note_text": None
        }
    ]
}
