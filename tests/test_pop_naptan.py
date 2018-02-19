"""
Testing the populate functions.
"""
import copy
import os
import io
import unittest
import datetime

import lxml.etree as et
from flask import current_app

from nextbus import create_app, db, models
from nextbus.populate.naptan import (_create_ind_parser, _get_naptan_data,
    _modify_stop_areas, _NaPTANStops, commit_naptan_data)
from nextbus.populate.nptg import (_get_nptg_data, _remove_districts,
                                   commit_nptg_data)
import test_db


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
NPTG_ALL = os.path.join(TEST_DIR, "NPTG_all.xml")
NPTG_RAW = os.path.join(TEST_DIR, "NPTG_raw.xml")
NPTG_TRAM = os.path.join(TEST_DIR, "NPTG_tram.xml")
NAPTAN_ALL = os.path.join(TEST_DIR, "NaPTAN_all.xml")
NAPTAN_RAW = os.path.join(TEST_DIR, "NaPTAN_raw.xml")
NAPTAN_RAW_370 = os.path.join(TEST_DIR, "NaPTAN_raw_370.xml")
NAPTAN_RAW_940 = os.path.join(TEST_DIR, "NaPTAN_raw_940.xml")
NAPTAN_TRAM = os.path.join(TEST_DIR, "NaPTAN_tram.xml")


class BaseXMLTests(unittest.TestCase):
    """ Base tests for comparing XML files. """
    # Use parser which removes blank text from transformed XML files
    parser = et.XMLParser(remove_blank_text=True)

    def assertXMLElementsEqual(self, e1, e2, msg=None, _path=None):
        """ Compares two XML Element objects by iterating through each
            tag recursively and comparing their tags, text, tails and
            attributes.
        """
        message = []
        # Check tags, text, tails, attributes and number of subelements
        if e1.tag != e2.tag:
            message.append("Tags %r != %r" % (e1.tag, e2.tag))
        if e1.text != e2.text:
            message.append("Text %r != %r" % (e1.text, e2.text))
        if e1.tail != e2.tail:
            message.append("Tail strings %r != %r" % (e1.tail, e2.tail))
        if e1.attrib != e2.attrib:
            message.append("Attributes %r != %r" % (e1.attrib, e1.attrib))
        if len(e1) != len(e2):
            message.append("%d != %d subelements" % (len(e1), len(e2)))

        # Errors found: create message and raise exception
        if message:
            if _path is not None and e1.tag == e2.tag:
                message.insert(0, "For element %s/%s:" % (_path, e1.tag))
            elif _path is not None and e1.tag != e2.tag:
                message.insert(0, "For subelements within %s:" % _path)

            new_msg = self._formatMessage(msg, "\n".join(message))
            raise self.failureException(new_msg)

        # If elements compared have children, iterate through them recursively
        if len(e1) > 0:
            new_path = e1.tag if _path is None else _path + "/" + e1.tag 
            for c1, c2 in zip(e1, e2):
                self.assertXMLElementsEqual(c1, c2, _path=new_path)


class NptgXsltTests(BaseXMLTests):
    """ Testing `_get_nptg_data` function which transforms NPTG data. """

    def test_nptg_transform_all_areas(self):
        data = _get_nptg_data(NPTG_RAW, atco_codes=None, out_file=None)

        expected = et.parse(NPTG_ALL, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())

    def test_nptg_transform_tram_only(self):
        data = _get_nptg_data(NPTG_RAW, atco_codes=[940], out_file=None)

        expected = et.parse(NPTG_TRAM, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())


class NaptanXsltTests(BaseXMLTests):
    """ Testing `_get_naptan_data` function which transforms NPTG data. """

    def test_naptan_transform_all_areas(self):
        data = _get_naptan_data([NAPTAN_RAW], list_area_codes=None,
                                out_file=None)

        expected = et.parse(NAPTAN_ALL, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())

    def test_naptan_transform_split_files(self):
        paths = [NAPTAN_RAW_370, NAPTAN_RAW_940]
        data = _get_naptan_data(paths, list_area_codes=None, out_file=None)
        expected = et.parse(NAPTAN_ALL, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())

    def test_naptan_trasform_tram_only(self):
        data = _get_naptan_data([NAPTAN_RAW], list_area_codes=["147"],
                              out_file=None)

        expected = et.parse(NAPTAN_TRAM, self.parser)
        self.assertXMLElementsEqual(data.getroot(), expected.getroot())


class ParseStopPointTests(unittest.TestCase):
    """ Testing the _NaPTANStops helper class which filters stop areas and
        add short indicators to stop points.
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


class PostprocessingTests(test_db.BaseDBTests):
    """ Testing functions which process data in the database after they have
        been populated.
    """
    def setUp(self):
        self.create_tables()

    def tearDown(self):
        self.drop_tables()

    def test_remove_districts(self):
        # Create another district but leave it without any localities
        new_district = copy.deepcopy(test_db.DISTRICT)
        new_district.update({
            "code": "247",
            "name": "Doncaster"
        })

        with self.app.app_context():
            objects = [
                models.Region(**test_db.REGION),
                models.AdminArea(**test_db.ADMIN_AREA),
                models.District(**test_db.DISTRICT),
                models.District(**new_district),
                models.Locality(**test_db.LOCALITY)
            ]
            db.session.add_all(objects)
            db.session.commit()
            # Remove orphaned districts
            _remove_districts()
            # Now check the districts; there should be only one
            districts = models.District.query.all()
            self.assertEqual(len(districts), 1)
            self.assertEqual(test_db.DISTRICT,
                             self.model_as_dict(districts[0]))

    def test_add_locality(self):
        modified_stop_area = copy.deepcopy(test_db.STOP_AREA)
        # Remove the locality code
        del modified_stop_area["locality_ref"]

        with self.app.app_context():
            objects = [
                models.Region(**test_db.REGION),
                models.AdminArea(**test_db.ADMIN_AREA),
                models.District(**test_db.DISTRICT),
                models.Locality(**test_db.LOCALITY),
                models.StopArea(**modified_stop_area),
                models.StopPoint(**test_db.STOP_POINT)
            ]
            db.session.add_all(objects)
            db.session.commit()
            # Identify the locality code and add it
            _modify_stop_areas()
            # Now check the stop areas; the single area should now have the
            # locality code
            area = models.StopArea.query.one()
            self.assertEqual(area.locality_ref,
                             test_db.STOP_AREA["locality_ref"])

    def test_remove_areas(self):
        new_stop_area = copy.deepcopy(test_db.STOP_AREA)
        new_stop_area.update({"code": "370G100808"})

        with self.app.app_context():
            objects = [
                models.Region(**test_db.REGION),
                models.AdminArea(**test_db.ADMIN_AREA),
                models.District(**test_db.DISTRICT),
                models.Locality(**test_db.LOCALITY),
                models.StopArea(**test_db.STOP_AREA),
                models.StopArea(**new_stop_area),
                models.StopPoint(**test_db.STOP_POINT)
            ]
            db.session.add_all(objects)
            db.session.commit()
            # Remove orphaned stop areas
            _modify_stop_areas()
            # Now check the stop areas; there should be only one
            areas = models.StopArea.query.all()
            self.assertEqual(len(areas), 1)
            self.assertEqual(test_db.STOP_AREA, self.model_as_dict(areas[0]))

class PopulateTests(test_db.BaseDBTests):

    def setUp(self):
        self.create_tables()

    def tearDown(self):
        self.drop_tables()

    def test_commit_nptg_data(self):
        with self.app.app_context():
            commit_nptg_data(nptg_file=NPTG_RAW)

            # Make queries to the DB to ensure data is populated correctly
            with self.subTest("region"):
                region_codes = (db.session.query(models.Region.code)
                                .order_by("code").all())
                self.assertEqual(region_codes, [("GB",), ("Y",)])

            with self.subTest("admin areas"):
                area_codes = (db.session.query(models.AdminArea.code)
                              .order_by("code").all())
                self.assertEqual(area_codes,
                    [("099",), ("110",), ("143",), ("145",), ("146",),
                     ("147",)]
                )

            with self.subTest("districts"):
                district_codes = (db.session.query(models.District.code)
                                  .order_by("code").all())
                # Should be only 1 district; the other has no associated
                # localities
                self.assertEqual(district_codes, [("263",)])

            with self.subTest("localities"):
                localities = models.Locality.query.all()
                self.assertEqual(len(localities), 3)

    def test_commit_naptan_data_no_nptg(self):
        with self.app.app_context(),\
                self.assertRaisesRegex(ValueError, "NPTG tables"):
            commit_naptan_data(naptan_files=[NAPTAN_RAW])

    def test_commit_naptan_data(self):
        with self.app.app_context():
            commit_nptg_data(nptg_file=NPTG_RAW)
            commit_naptan_data(naptan_files=[NAPTAN_RAW])

            # Make queries to the DB to ensure data is populated correctly
            with self.subTest("areas"):
                areas = models.StopArea.query.all()
                # Two stop areas do not have any stops, therefore 68 not 70
                self.assertEqual(len(areas), 46)

            with self.subTest("stops"):
                stops = models.StopPoint.query.all()
                self.assertEqual(len(stops), 174)
