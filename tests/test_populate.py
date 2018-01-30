"""
Testing the populate functions.
"""
import os
import io
import unittest
import datetime

import lxml.etree as et
from flask import current_app

from nextbus import create_app, models
from nextbus.populate.naptan import _get_atco_codes, _DBEntries
import test_database


NAPTAN_DATA = "NaPTAN_SW.xml"
NAPTAN_PROCESSED = "NaPTAN_processed.xml"


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


class EntryTests(unittest.TestCase):
    """ Tests on _DBEntries without database commits """

    def setUp(self):
        # Set up temporary file to be read by et.parse()
        xml_processed = io.BytesIO(
            b"<Data><Regions><Region><code>Y</code><name>Yorkshire</name>"
            b"<modified>2006-01-25T07:54:31</modified></Region></Regions>"
            b"</Data>"
        )
        self.db_e = _DBEntries(xml_processed)
    
    def tearDown(self):
        del self.db_e

    def test_add_items(self):
        self.db_e.add("Regions/Region", models.Region)
        region = {
            "code": "Y",
            "name": "Yorkshire",
            "modified": datetime.datetime(2006, 1, 25, 7, 54, 31)
        }
        self.assertEqual(self.db_e.entries[models.Region][0], region)
    
    def test_add_items_func(self):
        def func(ls, item):
            item["code"] = item["code"].lower()
            ls.append(item)
        self.db_e.add("Regions/Region", models.Region, parse=func)
        region = {
            "code": "y",
            "name": "Yorkshire",
            "modified": datetime.datetime(2006, 1, 25, 7, 54, 31)
        }
        self.assertEqual(self.db_e.entries[models.Region][0], region)
    
    def test_add_item_wrong_function(self):
        def func(ls, item, _):
            ls.append(item)
        with self.assertRaisesRegex(TypeError, "receive two arguments"):
            self.db_e.add("Regions/Region", models.Region, parse=func)


class EntryDBTests(test_database.DBTests):
    """ Tests on _DBEntries and committing changes to database """

    def setUp(self):
        self.create_tables()

    def tearDown(self):
        self.drop_tables()