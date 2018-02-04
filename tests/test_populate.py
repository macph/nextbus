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
from nextbus.populate.naptan import (_DBEntries, _get_atco_codes,
    _get_naptan_data, _get_nptg_data, _modify_stop_areas, _remove_districts,
    commit_naptan_data, commit_nptg_data)
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


class AtcoCodeTests(unittest.TestCase):
    """ Test the retrieval of ATCO codes from the config """

    def setUp(self):
        self.app = create_app()

    def tearDown(self):
        del self.app

    def test_default_codes(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = "all"
            self.assertEqual(_get_atco_codes(), None)

    def test_yorkshire_codes(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = [370, 450]
            self.assertEqual(_get_atco_codes(), [370, 450, 940])
    
    def test_invalid_type(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = ["string", 370]
            with self.assertRaisesRegex(ValueError, "must be integers"):
                _get_atco_codes()

    def test_invalid_string(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = "string"
            with self.assertRaisesRegex(ValueError, "must be set to either"):
                _get_atco_codes()

class EntryTests(unittest.TestCase):
    """ Tests on _DBEntries without database commits """
    xml = io.BytesIO(
        b"<Data><Regions><Region><code>Y</code><name>Yorkshire</name>"
        b"<modified>2006-01-25T07:54:31</modified></Region></Regions>"
        b"</Data>"
    )
    expected = {
        "code": "Y",
        "name": "Yorkshire",
        "modified": datetime.datetime(2006, 1, 25, 7, 54, 31)
    }

    def setUp(self):
        self.db_entries = _DBEntries(self.xml)
    
    def tearDown(self):
        del self.db_entries

    def test_add_items(self):
        self.db_entries.add("Regions/Region", models.Region)
        self.assertEqual(self.db_entries.entries[models.Region][0],
                         self.expected)
    
    def test_add_multiple(self):
        self.db_entries.add("Regions/Region", models.Region)
        self.db_entries.add("Regions/Region", models.Region)
        self.assertEqual(self.db_entries.entries[models.Region],
                         [self.expected] * 2)
    
    def test_add_items_func(self):
        def func(ls, item):
            item["name"] = item["name"].upper()
            ls.append(item)
        self.db_entries.add("Regions/Region", models.Region, func=func)
        region = {
            "code": "Y",
            "name": "YORKSHIRE",
            "modified": datetime.datetime(2006, 1, 25, 7, 54, 31)
        }
        self.assertEqual(self.db_entries.entries[models.Region][0], region)
    

    def test_add_conflict(self):
        self.db_entries.add("Regions/Region", models.Region, indices=("code",))
        conflict_entry = {
            "indices": ("code",),
            "columns": {"code", "name", "modified"}
        }
        self.assertEqual(self.db_entries.conflicts[models.Region],
                         conflict_entry)

    def test_add_item_wrong_function(self):
        def func(ls, item, _):
            ls.append(item)
        with self.assertRaisesRegex(TypeError, "receive two arguments"):
            self.db_entries.add("Regions/Region", models.Region, func=func)

    def test_add_item_multiple_constraints(self):
        with self.assertRaisesRegex(TypeError, "mutually exclusive"):
            self.db_entries.add("Regions/Region", models.Region,
                                indices=("code",), constraint="region_pkey")


class EntryDBTests(test_db.BaseDBTests):
    """ Tests on _DBEntries and committing changes to database """
    xml = io.BytesIO(
        b"<Data><Regions><Region><code>Y</code><name>Yorkshire</name>"
        b"<modified>2006-01-25T07:54:31</modified></Region></Regions>"
        b"</Data>"
    )

    def setUp(self):
        self.create_tables()
        # Set up temporary file to be read by et.parse()
        self.db_entries = _DBEntries(self.xml)

    def tearDown(self):
        self.drop_tables()
        del self.db_entries

    def test_insert_statement_no_conflict(self):
        self.db_entries.add("Regions/Region", models.Region)
        with self.app.app_context():
            insert = self.db_entries._create_insert_statement(models.Region)
            # Add binding to engine
            insert.bind = db.engine
            statement = str(insert)
            self.assertRegex(statement,
                r"INSERT INTO region \(code, name, modified\) VALUES"
            )
            self.assertNotRegex(statement, r"ON CONFLICT.+?DO UPDATE")

    def test_insert_statement_constraint(self):
        self.db_entries.add("Regions/Region", models.Region,
                            constraint="region_pkey")
        with self.app.app_context():
            insert = self.db_entries._create_insert_statement(models.Region)
            # Bind statement to database engine
            insert.bind = db.engine
            statement = str(insert)
            self.assertRegex(statement,
                r"INSERT INTO region \(code, name, modified\) "
                r"VALUES \(.+?\) ON CONFLICT ON CONSTRAINT region_pkey "
                r"DO UPDATE SET code = excluded.code, name = excluded.name, "
                r"modified = excluded.modified WHERE "
                r"region.modified < excluded.modified"
            )

    def test_insert_statement_column(self):
        self.db_entries.add("Regions/Region", models.Region, indices=("code",))
        with self.app.app_context():
            insert = self.db_entries._create_insert_statement(models.Region)
            # Bind statement to database engine
            insert.bind = db.engine
            statement = str(insert)
            self.assertRegex(statement,
                r"INSERT INTO region \(code, name, modified\) "
                r"VALUES \(.+?\) ON CONFLICT \(code\) "
                r"DO UPDATE SET code = excluded.code, name = excluded.name, "
                r"modified = excluded.modified WHERE "
                r"region.modified < excluded.modified"
            )

    def test_commit_changes(self):
        self.db_entries.add("Regions/Region", models.Region)
        with self.app.app_context():
            self.db_entries.commit()
            # Query the DB
            region = models.Region.query.one()
            self.assertEqual(
                (region.code, region.name, region.modified),
                ("Y", "Yorkshire", datetime.datetime(2006, 1, 25, 7, 54, 31))
            )


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
        del modified_stop_area["locality_code"]

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
            self.assertEqual(area.locality_code,
                             test_db.STOP_AREA["locality_code"])

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
