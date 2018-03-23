"""
Testing the populate functions.
"""
import copy
import os
import unittest

import lxml.etree as et

from nextbus import db, models
from nextbus.populate.naptan import (_create_ind_parser, _get_naptan_data,
    _remove_stop_areas, _set_stop_area_locality, commit_naptan_data)
from nextbus.populate.nptg import (_get_nptg_data, _remove_districts,
                                   commit_nptg_data)
import utils


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
NPTG_ALL = os.path.join(TEST_DIR, "NPTG_all.xml")
NPTG_RAW = os.path.join(TEST_DIR, "NPTG_raw.xml")
NPTG_TRAM = os.path.join(TEST_DIR, "NPTG_tram.xml")
NAPTAN_ALL = os.path.join(TEST_DIR, "NaPTAN_all.xml")
NAPTAN_RAW = os.path.join(TEST_DIR, "NaPTAN_raw.xml")
NAPTAN_RAW_370 = os.path.join(TEST_DIR, "NaPTAN_raw_370.xml")
NAPTAN_RAW_940 = os.path.join(TEST_DIR, "NaPTAN_raw_940.xml")
NAPTAN_TRAM = os.path.join(TEST_DIR, "NaPTAN_tram.xml")


class NptgXsltTests(utils.BaseXMLTests):
    """ Testing `_get_nptg_data` function which transforms NPTG data. """

    def test_nptg_transform_all_areas(self):
        data = _get_nptg_data(iter([NPTG_RAW]))

        expected = et.parse(NPTG_ALL, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())

    def test_nptg_transform_tram_only(self):
        data = _get_nptg_data(iter([NPTG_RAW]), atco_codes=[940])

        expected = et.parse(NPTG_TRAM, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())


class NaptanXsltTests(utils.BaseXMLTests):
    """ Testing `_get_naptan_data` function which transforms NPTG data. """

    def test_naptan_transform_all_areas(self):
        data = _get_naptan_data(iter([NAPTAN_RAW]))

        expected = et.parse(NAPTAN_ALL, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())

    def test_naptan_transform_split_files(self):
        iter_paths = iter([NAPTAN_RAW_370, NAPTAN_RAW_940])
        data = _get_naptan_data(iter_paths)
        expected = et.parse(NAPTAN_ALL, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())

    def test_naptan_trasform_tram_only(self):
        data = _get_naptan_data(iter([NAPTAN_RAW]), list_area_codes=["147"])

        expected = et.parse(NAPTAN_TRAM, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())


class ParseStopPointTests(unittest.TestCase):
    """ Testing the stop indicator parser which adds short indicators to
        stop points.
    """
    indicators = [
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
        ("E-bound", ">E"),
        ("East-bound", ">E"),
        ("Gate K", "K"),
        (">N", ">N"),
        ("->N", ">N"),
        ("n-bound", ">N"),
        ("near", "near"),
        ("near Crossing", "near CROS."),
        ("ne-bound", ">NE"),
        ("NET NW- bound", "NET >NW"),
        ("northbound", ">N"),
        ("North Bound", ">N"),
        ("Near", "near"),
        ("nr", "near"),
        ("near Electric Substation", "near ELEC."),
        ("nw-bound", ">NW"),
        ("opp.", "opp"),
        ("OPp", "opp"),
        ("opp 23 Main Street", "opp 23"),
        ("opp and after", "opp aft"),
        ("opposite 10", "opp 10"),
        ("o/s", "o/s"),
        ("O/S", "o/s"),
        ("o/s 107/109", "o/s 107/."),
        ("Outside 462", "o/s 462"),
        ("Platform 1", "1"),
        ("s-bound", ">S"),
        ("SBound", ">S"),
        ("S-bound adj", ">S adj"),
        ("SE bound", ">SE"),
        ("->SE", ">SE"), 
        ("stance", ""),
        ("Stance 20", "20"),
        ("Stand", ""), ("Stand 0", "0"),
        ("stop", ""),
        ("Stop 14a", "14A"),
        ("Stop 3 eastbound", "3 >E"),
        ("Stop CU", "CU"),
        ("Stop ->S", ">S"),
        ("->SW", ">SW"),
        ("sw-bound", ">SW"),
        ("To Cathedral", "to CATH."),
        ("twixt bus station and Church Street", "TWIXT BUS"),
        ("W - Bound", ">W"),
        ("Westbound", ">W")
    ]

    def setUp(self):
        self.parser = _create_ind_parser()
    
    def tearDown(self):
        del self.parser

    def test_short_ind(self):
        for ind, expected in self.indicators:
            with self.subTest(indicator=ind):
                self.assertEqual(self.parser(ind), expected)


class PostprocessingTests(utils.BaseAppTests):
    """ Testing functions which process data in the database after they have
        been populated.
    """
    def setUp(self):
        self.create_tables()

    def tearDown(self):
        self.drop_tables()

    def test_remove_districts(self):
        # Create another district but leave it without any localities
        new_district = copy.deepcopy(utils.DISTRICT)
        new_district.update({
            "code": "247",
            "name": "Doncaster"
        })

        objects = [
            models.Region(**utils.REGION),
            models.AdminArea(**utils.ADMIN_AREA),
            models.District(**utils.DISTRICT),
            models.District(**new_district),
            models.Locality(**utils.LOCALITY)
        ]
        db.session.add_all(objects)
        db.session.commit()
        # Remove orphaned districts
        _remove_districts()
        # Now check the districts; there should be only one
        districts = models.District.query.all()
        self.assertEqual(len(districts), 1)
        self.assertEqual(utils.DISTRICT, self.model_as_dict(districts[0]))

    def test_add_locality(self):
        modified_stop_area = copy.deepcopy(utils.STOP_AREA)
        # Remove the locality code
        del modified_stop_area["locality_ref"]

        objects = [
            models.Region(**utils.REGION),
            models.AdminArea(**utils.ADMIN_AREA),
            models.District(**utils.DISTRICT),
            models.Locality(**utils.LOCALITY),
            models.StopArea(**modified_stop_area),
            models.StopPoint(**utils.STOP_POINT)
        ]
        db.session.add_all(objects)
        db.session.commit()
        # Identify the locality code and add it
        _set_stop_area_locality()
        # Now check the stop areas; the single area should now have the
        # locality code
        area = models.StopArea.query.one()
        self.assertEqual(area.locality_ref, utils.STOP_AREA["locality_ref"])

    def test_add_locality_multiple(self):
        new_locality = copy.deepcopy(utils.LOCALITY)
        modified_stop_area = copy.deepcopy(utils.STOP_AREA)
        new_stop_point = copy.deepcopy(utils.STOP_POINT)
        # Modify locality to be different from that of LOCALITY
        new_locality.update({
            "code": "N0060732", "name": "Hunters Bar", "easting": 433217,
            "northing": 385748, "longitude": -1.502266, "latitude": 53.36756
        })
        del modified_stop_area["locality_ref"] # Remove the locality code
        # Modify stop point to be different from that of STOP_POINT but
        # still have the same stop area
        new_stop_point.update({
            "atco_code": "370020581", "naptan_code": "37020581",
            "name": "Rustlings Road", "locality_ref": "N0060732"
        })

        objects = [
            models.Region(**utils.REGION),
            models.AdminArea(**utils.ADMIN_AREA),
            models.District(**utils.DISTRICT),
            models.Locality(**utils.LOCALITY),
            models.Locality(**new_locality),
            models.StopArea(**modified_stop_area),
            models.StopPoint(**utils.STOP_POINT),
            models.StopPoint(**new_stop_point)
        ]
        db.session.add_all(objects)
        db.session.commit()

        _set_stop_area_locality()

        area = models.StopArea.query.one()
        self.assertEqual(area.locality_ref, utils.STOP_AREA["locality_ref"])

    def test_remove_areas(self):
        new_stop_area = copy.deepcopy(utils.STOP_AREA)
        new_stop_area.update({"code": "370G100808"})

        objects = [
            models.Region(**utils.REGION),
            models.AdminArea(**utils.ADMIN_AREA),
            models.District(**utils.DISTRICT),
            models.Locality(**utils.LOCALITY),
            models.StopArea(**utils.STOP_AREA),
            models.StopArea(**new_stop_area),
            models.StopPoint(**utils.STOP_POINT)
        ]
        db.session.add_all(objects)
        db.session.commit()
        # Remove orphaned stop areas
        _remove_stop_areas()
        # Now check the stop areas; there should be only one
        areas = models.StopArea.query.one()
        self.assertEqual(utils.STOP_AREA, self.model_as_dict(areas))

class PopulateTests(utils.BaseAppTests):

    def setUp(self):
        self.create_tables()

    def tearDown(self):
        self.drop_tables()

    def test_commit_nptg_data(self):
        commit_nptg_data(list_files=[NPTG_RAW])

        # Make queries to the DB to ensure data is populated correctly
        with self.subTest("region"):
            region_codes = (db.session.query(models.Region.code)
                            .order_by("code").all())
            self.assertEqual(region_codes, [("GB",), ("Y",)])

        with self.subTest("admin areas"):
            area_codes = (db.session.query(models.AdminArea.code)
                          .order_by("code").all())
            self.assertEqual(area_codes,
                [("099",), ("110",), ("143",), ("145",), ("146",), ("147",)]
            )

        with self.subTest("districts"):
            district_codes = (db.session.query(models.District.code)
                              .order_by("code").all())
            # Should be only 1 district; the other has no associated localities
            self.assertEqual(district_codes, [("263",)])

        with self.subTest("localities"):
            localities = models.Locality.query.all()
            self.assertEqual(len(localities), 3)

    def test_commit_naptan_data_no_nptg(self):
        with self.assertRaisesRegex(ValueError, "NPTG tables"):
            commit_naptan_data(list_files=[NAPTAN_RAW])

    def test_commit_naptan_data(self):
        commit_nptg_data(list_files=[NPTG_RAW])
        commit_naptan_data(list_files=[NAPTAN_RAW])

        # Make queries to the DB to ensure data is populated correctly
        with self.subTest("areas"):
            areas = models.StopArea.query.all()
            # Two stop areas do not have any stops, therefore 68 not 70
            self.assertEqual(len(areas), 46)

        with self.subTest("stops"):
            stops = models.StopPoint.query.all()
            self.assertEqual(len(stops), 174)
