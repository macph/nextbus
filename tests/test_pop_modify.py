"""
Testing the modification functions for processing populated data.
"""
import copy
import os
import io
import unittest
import datetime

import lxml.etree as et
from flask import current_app

from nextbus import create_app, db, models
import nextbus.populate.modify as mod
import test_db

MODIFY_XML = b"""\
<data>
  <table model="Region">
    <create>
      <code>L</code>
      <name>London</name>
      <modified>2006-01-25T07:54:31</modified>
      <tsv_name/>
    </create>
    <create>
      <code>Y</code>
      <name>Yorkshire</name>
      <modified>2006-01-25T07:54:31</modified>
      <tsv_name/>
    </create>
  </table>
  <table model="Region">
    <replace code="L">
      <name old="London">Greater London</name>
    </replace>
    <delete code="Y"/>
  </table>
</data>
"""

def create_subelement(parent, tag, attrib=None, text=None):
    """ Helper function to add subelements and text at the same time. """
    new_element = et.SubElement(parent, tag, attrib=attrib)
    if text is not None:
        new_element.text = text

class CreateEntryTests(test_db.BaseDBTests):
    """ Testing the ``_create_rows()`` function for adding new rows after
        population.
    """
    def setUp(self):
        self.create_tables()
        self.md = mod._ModifyData(None)

    def tearDown(self):
        self.drop_tables()
        del self.md

    def test_rows_added(self):
        c_london = et.Element("create")
        create_subelement(c_london, "code", text="L")
        create_subelement(c_london, "name", text="London")
        create_subelement(c_london, "modified", text="2006-01-25T07:54:31")

        c_yorkshire = et.Element("create")
        create_subelement(c_yorkshire, "code", text="Y")
        create_subelement(c_yorkshire, "name", text="Yorkshire")
        create_subelement(c_yorkshire, "modified", text="2006-01-25T07:54:31")

        with self.app.app_context():
            self.md._create_row(models.Region, [c_london, c_yorkshire])

        with self.app.app_context():
            regions = models.Region.query.order_by("code").all()
            self.assertEqual(len(regions), 2)
            self.assertEqual([regions[0].code, regions[0].name],
                             ["L", "London"])
            self.assertEqual([regions[1].code, regions[1].name],
                             ["Y", "Yorkshire"])


class DeleteEntryTests(test_db.BaseDBTests):
    """ Testing the ``_delete_rows()`` function for deleting rows after
        population.
    """
    def setUp(self):
        self.create_tables()
        self.md = mod._ModifyData(None)
        with self.app.app_context():
            region = models.Region(**test_db.REGION)
            db.session.add(region)
            db.session.commit()
            db.session.close()

    def tearDown(self):
        self.drop_tables()
        del self.md

    def test_row_deleted(self):
        d_yorkshire = et.Element("delete", attrib={"code": "Y"})
        with self.app.app_context():
            self.md._delete_row(models.Region, [d_yorkshire])
        
        with self.app.app_context():
            regions = models.Region.query.all()
            self.assertFalse(regions)

    def test_row_deleted_no_match(self):
        d_london = et.Element("delete", attrib={"code": "L"})
        with self.app.app_context():
            self.md._delete_row(models.Region, [d_london])
            self.assertEqual(self.md.issues, ["No rows matching {'code': 'L'} "
                                              "for model 'Region'"])


class ReplaceEntryTests(test_db.BaseDBTests):
    """ Testing the ``_replace_rows()`` function for modifying rows after
        population.
    """
    def setUp(self):
        self.create_tables()
        self.md = mod._ModifyData(None)
        with self.app.app_context():
            region = models.Region(**test_db.REGION)
            db.session.add(region)
            db.session.commit()
            db.session.close()

    def tearDown(self):
        self.drop_tables()
        del self.md

    def test_row_replaced(self):
        r_yorkshire = et.Element("replace", attrib={"code": "Y"})
        create_subelement(r_yorkshire, "name", text="Greater Yorkshire")
        with self.app.app_context():
            self.md._replace_row(models.Region, [r_yorkshire])

        with self.app.app_context():
            regions = models.Region.query.all()
            self.assertEqual(len(regions), 1)
            self.assertEqual(regions[0].name, "Greater Yorkshire")
    
    def test_row_replaced_correct_value(self):
        r_yorkshire = et.Element("replace", attrib={"code": "Y"})
        create_subelement(r_yorkshire, "name", attrib={"old": "Yorkshire"},
                          text="Greater Yorkshire")
        with self.app.app_context():
            self.md._replace_row(models.Region, [r_yorkshire])
            self.assertFalse(self.md.issues)

    def test_row_replaced_incorrect_value(self):
        r_yorkshire = et.Element("replace", attrib={"code": "Y"})
        create_subelement(r_yorkshire, "name",
                          attrib={"old": "Greater Yorkshire"},
                          text="Lesser Yorkshire")
        with self.app.app_context():
            self.md._replace_row(models.Region, [r_yorkshire])
            self.assertEqual(self.md.issues[0],
                             "Region.name: 'Greater Yorkshire' for {'code': "
                             "'Y'} does not match {'Yorkshire'}.")

    def test_row_replaced_value_exists(self):
        r_yorkshire = et.Element("replace", attrib={"code": "Y"})
        create_subelement(r_yorkshire, "name",
                          attrib={"old": "Greater Yorkshire"},
                          text="Yorkshire")
        with self.app.app_context():
            self.md._replace_row(models.Region, [r_yorkshire])
            self.assertEqual(self.md.issues[0],
                             "Region.name: 'Yorkshire' for {'code': 'Y'} "
                             "already matches {'Yorkshire'}.")

    def test_row_replaced_no_match(self):
        r_london = et.Element("replace", attrib={"code": "L"})
        create_subelement(r_london, "name", attrib={"old": "London"},
                          text="Greater London")
        with self.app.app_context():
            self.md._replace_row(models.Region, [r_london])
            self.assertEqual(self.md.issues, ["No rows matching {'code': 'L'} "
                                              "for model 'Region'"])

class ModifyDataTests(test_db.BaseDBTests):
    """ Testing ``_ModifyData.process()`` and ``modify_data()`` functions.
    """
    def setUp(self):
        self.create_tables()
        self.data = copy.copy(MODIFY_XML)

    def tearDown(self):
        self.drop_tables()
        del self.data

    def test_modify_data(self):
        xml_data = io.BytesIO(self.data)
        with self.app.app_context():
            mod.modify_data(xml_data)
            regions = models.Region.query.all()
            self.assertEqual(len(regions), 1)
            self.assertEqual([regions[0].code, regions[0].name],
                             ["L", "Greater London"])

    def test_modify_data_no_model(self):
        self.data = self.data.replace(b' model="Region"', b"")
        xml_data = io.BytesIO(self.data)
        with self.app.app_context(),\
                self.assertRaisesRegex(ValueError, "Every <table> element"):
            mod.modify_data(xml_data)

    def test_modify_data_incorrect_model(self):
        self.data = self.data.replace(b'model="Region"', b'model="SomeTable"')
        xml_data = io.BytesIO(self.data)
        with self.app.app_context(),\
                self.assertRaisesRegex(ValueError, "Every <table> element"):
            mod.modify_data(xml_data)
