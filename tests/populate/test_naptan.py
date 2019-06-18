"""
Testing the populate functions.
"""
import os

import lxml.etree as et
import pytest

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate.utils import xslt_transform
from nextbus.populate.naptan import (
    NAPTAN_XSLT, _create_ind_parser, _remove_stop_areas,
    _set_stop_area_locality, _setup_naptan_functions, commit_naptan_data
)
from nextbus.populate.nptg import NPTG_XSLT, _remove_districts, commit_nptg_data


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
NPTG_ALL = os.path.join(TEST_DIR, "NPTG_all.xml")
NPTG_RAW = os.path.join(TEST_DIR, "NPTG_raw.xml")
NAPTAN_ALL = os.path.join(TEST_DIR, "NaPTAN_all.xml")
NAPTAN_RAW = os.path.join(TEST_DIR, "NaPTAN_raw.xml")
NAPTAN_RAW_370 = os.path.join(TEST_DIR, "NaPTAN_raw_370.xml")
NAPTAN_RAW_940 = os.path.join(TEST_DIR, "NaPTAN_raw_940.xml")

NPTG_XSLT = os.path.join(ROOT_DIR, NPTG_XSLT)
NAPTAN_XSLT = os.path.join(ROOT_DIR, NAPTAN_XSLT)

PARSER = et.XMLParser(remove_blank_text=True)


def test_nptg_transform_all(asserts):
    data = xslt_transform(NPTG_RAW, et.XSLT(et.parse(NPTG_XSLT)))
    expected = et.parse(NPTG_ALL, et.XMLParser(remove_blank_text=True))

    asserts.xml_elements_equal(data.getroot(), expected.getroot())


def test_naptan_transform_all(asserts):
    _setup_naptan_functions()
    data = xslt_transform(NAPTAN_RAW, et.XSLT(et.parse(NAPTAN_XSLT)))
    expected = et.parse(NAPTAN_ALL, PARSER)

    asserts.xml_elements_equal(data.getroot(), expected.getroot())


@pytest.mark.parametrize("original, expected", [
    ("22000003", "2200."),
    ("24m East of Balgownie Way", "24M EAST"),
    ("4 Victoria St", "4 VICT."),
    ("Adj", "adj"),
    ("adj New Road", "adj NEW"),
    ("after", "aft"),
    ("after Phone Box", "aft PHONE"),
    ("at", "at"),
    ("at No. 7", "at 7"),
    ("bay 14", "14"),
    ("before", "bef"),
    ("before Phone Box", "bef PHONE"),
    ("By", "by"),
    ("by Post box", "by POST"),
    ("corner", "cnr"),
    ("corner of Orange Grove", "cnr OF"),
    ("E-bound", "->E"),
    ("East-bound", "->E"),
    ("Gate K", "K"),
    (">N", "->N"),
    ("->N", "->N"),
    ("n-bound", "->N"),
    ("near", "near"),
    ("near Crossing", "near CROS."),
    ("ne-bound", "->NE"),
    ("NET NW- bound", "NET ->NW"),
    ("northbound", "->N"),
    ("North Bound", "->N"),
    ("Near", "near"),
    ("nr", "near"),
    ("near Electric Substation", "near ELEC."),
    ("nw-bound", "->NW"),
    ("opp.", "opp"),
    ("OPp", "opp"),
    ("opp 23 Main Street", "opp 23"),
    ("opp and after", "opp aft"),
    ("opposite no 10", "opp 10"),
    ("o/s", "o/s"),
    ("O/S", "o/s"),
    ("o/s 107/109", "o/s 107/."),
    ("Outside 462", "o/s 462"),
    ("Platform 1", "1"),
    ("s-bound", "->S"),
    ("SBound", "->S"),
    ("S-bound adj", "->S adj"),
    ("SE bound", "->SE"),
    ("->SE", "->SE"),
    ("stance", ""),
    ("Stance 20", "20"),
    ("Stand", ""), ("Stand 0", "0"),
    ("stop", ""),
    ("Stop 14a", "14A"),
    ("Stop 3 eastbound", "3 ->E"),
    ("Stop CU", "CU"),
    ("Stop ->S", "->S"),
    ("->SW", "->SW"),
    ("sw-bound", "->SW"),
    ("To Cathedral", "to CATH."),
    ("twixt bus station and Church Street", "TWIXT BUS"),
    ("W - Bound", "->W"),
    ("Westbound", "->W")
])
def test_short_ind_parser(original, expected):
    assert _create_ind_parser()(original) == expected


def test_remove_districts(load_db):
    # New district without any localities
    new_district = models.District(code="286", name="Greenwich",
                                   admin_area_ref="082")
    db.session.add(new_district)
    db.session.commit()

    districts = models.District.query.order_by("code").all()
    expected = [("276", "Barking and Dagenham"), ("286", "Greenwich")]
    assert [(d.code, d.name) for d in districts] == expected

    # Remove orphaned districts
    _remove_districts()
    districts = models.District.query.order_by("code").all()
    expected = [("276", "Barking and Dagenham")]
    assert [(d.code, d.name) for d in districts] == expected


def test_add_locality(load_db):
    models.StopArea.query.update({"locality_ref": None})
    db.session.commit()

    stop_areas = models.StopArea.query.order_by("code").all()
    expected = [("490G00008638", None), ("490G00015G", None)]
    assert [(sa.code, sa.locality_ref) for sa in stop_areas] == expected

    # Identify the locality code and add it
    _set_stop_area_locality()
    stop_areas = models.StopArea.query.order_by("code").all()
    expected = [("490G00008638", "N0059951"), ("490G00015G", "N0059951")]
    assert [(sa.code, sa.locality_ref) for sa in stop_areas] == expected


def test_add_locality_multiple(load_db):
    # Add new locality nearby
    new_locality = models.Locality(
        code="E0033933",
        name="Creekmouth",
        easting=545640,
        northing=182140,
        longitude=0.09771661,
        latitude=51.51941,
        admin_area_ref="082",
        district_ref="276",
        parent_ref="N0060403"
    )
    db.session.add(new_locality)
    # Set one of the stop points to this locality
    stop_point = models.StopPoint.query.get("490008638N")
    stop_point.locality_ref = "E0033933"
    # Remove stop area locality ref
    stop_area = models.StopArea.query.get("490G00008638")
    stop_area.locality_ref = None
    db.session.commit()

    def query_stop_points():
        stop_points = (
            models.StopPoint.query
            .filter(models.StopPoint.stop_area_ref == "490G00008638")
            .order_by("atco_code")
            .all()
        )
        return [(sp.atco_code, sp.locality_ref) for sp in stop_points]

    # Localities should be split for area
    expected = [("490008638N", "E0033933"), ("490008638S", "N0059951")]
    assert query_stop_points() == expected

    _set_stop_area_locality()
    # Stop area should have new locality_ref while stop points unchanged
    assert models.StopArea.query.get("490G00008638").locality_ref == "N0059951"
    assert query_stop_points() == expected


def test_remove_areas(load_db):
    new_stop_area = models.StopArea(
        code="490G00003616",
        name="Barking Town Centre",
        stop_area_type="GCLS",
        active=True,
        easting=544229,
        northing=184176,
        longitude=0.07822732541,
        latitude=51.5380673333,
        admin_area_ref="082",
        locality_ref="N0059951"
    )
    db.session.add(new_stop_area)
    db.session.commit()

    _remove_stop_areas()
    # Now check the stop areas; there should be only two
    stop_areas = models.StopArea.query.order_by("code").all()
    expected = [("490G00008638", "Greatfields Park"),
                ("490G00015G", "Barking Station")]
    assert [(sa.code, sa.name) for sa in stop_areas] == expected


def test_commit_nptg_data(create_db):
    commit_nptg_data(list_files=[NPTG_RAW])

    data = {
        "r": db.session.query(models.Region.code).order_by("code").all(),
        "a": db.session.query(models.AdminArea.code).order_by("code").all(),
        "d": db.session.query(models.District.code).order_by("code").all(),
        "l": db.session.query(models.Locality.code).order_by("code").all(),
    }
    data = {model: [i[0] for i in data[model]] for model in data}

    assert data == {
        "r": ["GB", "Y"],
        "a": ["099", "147"],
        "d": ["263"],
        "l": ["E0029982", "E0057890", "N0060732"]
    }


def test_commit_naptan_data_no_nptg(create_db):
    with pytest.raises(ValueError, match="NPTG tables are not populated"):
        commit_naptan_data(list_files=[NAPTAN_RAW])


NAPTAN_EXPECTED = {
    "a": [
        "370G100004", "370G100020", "370G100887", "370G100888", "370G100890",
        "370G100955", "370G100959", "940GZZSYSHU", "940GZZSYWTS"
    ],
    "p": [
        "370010113", "370010114", "370010115", "370010119", "370010120",
        "370010121", "370010122", "370010123", "370010124", "370010125",
        "370010126", "370010127", "370010128", "370010130", "370010131",
        "370010132", "370010133", "370010134", "370010140", "370010143",
        "370010216", "370010217", "370010218", "370010219", "370010231",
        "370010232", "370010233", "370010234", "370020360", "370020361",
        "370020378", "370020581", "370020582", "370020621", "370020622",
        "370020637", "370020638", "370022809", "370022846", "370022848",
        "370023677", "370026733", "9400ZZSYSHU1", "9400ZZSYSHU2",
        "9400ZZSYWTS1", "9400ZZSYWTS2"
    ]
}


def _collect_naptan_data():
    data = {
        "a": db.session.query(models.StopArea.code).order_by("code").all(),
        "p": db.session.query(models.StopPoint.atco_code)
                       .order_by("atco_code").all(),
    }
    return {model: [i[0] for i in data[model]] for model in data}


def test_commit_naptan_data(create_db):
    commit_nptg_data(list_files=[NPTG_RAW])
    commit_naptan_data(list_files=[NAPTAN_RAW])

    assert _collect_naptan_data() == NAPTAN_EXPECTED


def test_commit_naptan_data_multiple_files(create_db):
    commit_nptg_data(list_files=[NPTG_RAW])
    commit_naptan_data(list_files=[NAPTAN_RAW_370, NAPTAN_RAW_940])

    assert _collect_naptan_data() == NAPTAN_EXPECTED
