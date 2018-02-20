"""
Testing the extension functions for XSLT transformations and the element ->
dict function.
"""
import datetime
import io
import os
import unittest

from flask import current_app
import lxml.etree as et

from nextbus import db, create_app, models
from nextbus.populate import (DBEntries, element_as_dict, ext_element_text,
                              get_atco_codes, XSLTExtFunctions)
import test_db


class ElementDictTests(unittest.TestCase):
    """ Testing the ``_element_as_dict`` function. """

    def setUp(self):
        self.element = et.Element("data")
        for i in range(10):
            sub = et.SubElement(self.element, "tag%d" % i)
            sub.text = "content %d" % i
        self.expected = {"tag%d" % i: "content %d" % i for i in range(10)}

    def tearDown(self):
        del self.element
        del self.expected

    def test_element_to_dict(self):
        new_dict = element_as_dict(self.element)
        self.assertEqual(new_dict, self.expected)

    def test_element_upper(self):
        upper = lambda s: s.upper()
        new_dict = element_as_dict(self.element, tag5=upper)
        self.expected["tag5"] = self.expected["tag5"].upper()
        self.assertEqual(new_dict, self.expected)

    def test_element_wrong_key(self):
        upper = lambda s: s.upper()
        with self.assertRaises(ValueError):
            new_dict = element_as_dict(self.element, tag10=upper)

    def test_element_wrong_function(self):
        replace = lambda s, o, n: s.replace(o, n)
        with self.assertRaisesRegex(TypeError, "only one argument"):
            new_dict = element_as_dict(self.element, tag5=replace)


class ElementTextTests(unittest.TestCase):
    """ Testing the ``_element_text`` decorator which passes XPath queries
        in the form of lists of XML elements as text to the extension
        functions.
    """

    @staticmethod
    @ext_element_text
    def passthrough(instance, context, result, *args, **kwargs):
        """ Simple function to pass through all arguments """
        return instance, context, result, args, kwargs

    def test_decorator_one_element(self):
        result = [et.Element("name")]
        result[0].text = "text content"
        output = self.passthrough(None, None, result)
        self.assertEqual(output[2], "text content")

    def test_decorator_one_string(self):
        result = ["text content"]
        output = self.passthrough(None, None, result)
        self.assertEqual(output[2], "text content")

    def test_decorator_empty(self):
        result = []
        output = self.passthrough(None, None, result)
        self.assertEqual(output, None)

    def test_decorator_multiple(self):
        result = [et.Element("name"), "text content 2"]
        result[0].text = "text content 1"
        with self.assertRaises(ValueError):
            output = self.passthrough(None, None, result)


class ExtensionTests(unittest.TestCase):
    """ Testing all methonds in the ``_ExtFunctions`` class. """

    def setUp(self):
        self.ext = XSLTExtFunctions()
        self.result = [et.Element("name")]

    def tearDown(self):
        del self.ext
        del self.result

    def test_ext_replace_string(self):
        self.result[0].text = "Upper Warlingham"
        self.assertEqual(self.ext.replace(None, self.result, "Warl", "Wold"),
                         "Upper Woldingham")

    def test_ext_upper_string(self):
        self.result[0].text = "East Grinstead"
        self.assertEqual(self.ext.upper(None, self.result), "EAST GRINSTEAD")

    def test_ext_lower_string(self):
        self.result[0].text = "East Grinstead"
        self.assertEqual(self.ext.lower(None, self.result), "east grinstead")

    def test_ext_capitalize_string(self):
        self.result[0].text = "St james's GATE (stop D)"
        self.assertEqual(self.ext.capitalize(None, self.result),
                         "St James's Gate (Stop D)")

class AtcoCodeTests(unittest.TestCase):
    """ Test the retrieval of ATCO codes from the config """

    def setUp(self):
        self.app = create_app(config_obj="default_config.TestConfig")

    def tearDown(self):
        del self.app

    def test_default_codes(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = "all"
            self.assertEqual(get_atco_codes(), None)

    def test_yorkshire_codes(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = [370, 450]
            self.assertEqual(get_atco_codes(), [370, 450, 940])
    
    def test_invalid_type(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = ["string", 370]
            with self.assertRaisesRegex(ValueError, "must be integers"):
                get_atco_codes()

    def test_invalid_string(self):
        with self.app.app_context():
            current_app.config["ATCO_CODES"] = "string"
            with self.assertRaisesRegex(ValueError, "must be set to either"):
                get_atco_codes()

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
        self.db_entries = DBEntries(self.xml)
    
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
        b"<modified>2006-01-25T07:54:31</modified><tsv_name/></Region>"
        b"</Regions></Data>"
    )

    def setUp(self):
        self.create_tables()
        # Set up temporary file to be read by et.parse()
        self.db_entries = DBEntries(self.xml)

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
                r"INSERT INTO region \(code, name, modified, tsv_name\) VALUES"
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
                r"INSERT INTO region \(code, name, modified, tsv_name\) "
                r"VALUES \(.+?\) ON CONFLICT ON CONSTRAINT region_pkey "
                r"DO UPDATE SET code = excluded.code, name = excluded.name, "
                r"modified = excluded.modified, tsv_name = excluded.tsv_name "
                r"WHERE region.modified < excluded.modified"
            )

    def test_insert_statement_column(self):
        self.db_entries.add("Regions/Region", models.Region, indices=("code",))
        with self.app.app_context():
            insert = self.db_entries._create_insert_statement(models.Region)
            # Bind statement to database engine
            insert.bind = db.engine
            statement = str(insert)
            self.assertRegex(statement,
                r"INSERT INTO region \(code, name, modified, tsv_name\) "
                r"VALUES \(.+?\) ON CONFLICT \(code\) "
                r"DO UPDATE SET code = excluded.code, name = excluded.name, "
                r"modified = excluded.modified, tsv_name = excluded.tsv_name "
                r"WHERE region.modified < excluded.modified"
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
