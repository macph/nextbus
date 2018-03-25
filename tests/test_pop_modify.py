"""
Testing the modification functions for processing populated data.
"""
import copy
import io

import lxml.etree as et

from nextbus import db, models
from nextbus.populate import database_session
from nextbus.populate.modify import _create, _delete, _replace, modify_data
import utils


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


class CreateEntryTests(utils.BaseAppTests):
    """ Testing the ``_create_rows()`` function for adding new rows after
        population.
    """
    def setUp(self):
        self.create_tables()

    def tearDown(self):
        self.drop_tables()

    def test_rows_added(self):
        c_london = et.Element("create")
        create_subelement(c_london, "code", text="L")
        create_subelement(c_london, "name", text="London")
        create_subelement(c_london, "modified", text="2006-01-25T07:54:31")

        c_yorkshire = et.Element("create")
        create_subelement(c_yorkshire, "code", text="Y")
        create_subelement(c_yorkshire, "name", text="Yorkshire")
        create_subelement(c_yorkshire, "modified", text="2006-01-25T07:54:31")

        with database_session():
            _create(models.Region, c_london)
            _create(models.Region, c_yorkshire)

        regions = models.Region.query.order_by("code").all()
        self.assertEqual(len(regions), 2)
        self.assertEqual([regions[0].code, regions[0].name], ["L", "London"])
        self.assertEqual([regions[1].code, regions[1].name],
                         ["Y", "Yorkshire"])


class DeleteEntryTests(utils.BaseAppTests):
    """ Testing the ``_delete_rows()`` function for deleting rows after
        population.
    """
    def setUp(self):
        self.create_tables()
        with self.app.app_context():
            region = models.Region(**utils.REGION)
            db.session.add(region)
            db.session.commit()
            db.session.close()

    def tearDown(self):
        self.drop_tables()

    def test_row_deleted(self):
        d_yorkshire = et.Element("delete", attrib={"code": "Y"})
        with database_session():
            _delete(models.Region, d_yorkshire)

        regions = models.Region.query.all()
        self.assertFalse(regions)

    def test_row_deleted_no_match(self):
        d_london = et.Element("delete", attrib={"code": "L"})
        with database_session(), self.assertLogs("populate.modify") as log:
            _delete(models.Region, d_london)

        self.assertIn("No rows matching {'code': 'L'} for model 'Region'",
                      log.output[0])


class ReplaceEntryTests(utils.BaseAppTests):
    """ Testing the ``_replace_rows()`` function for modifying rows after
        population.
    """
    def setUp(self):
        self.create_tables()
        with self.app.app_context():
            region = models.Region(**utils.REGION)
            db.session.add(region)
            db.session.commit()
            db.session.close()

    def tearDown(self):
        self.drop_tables()

    def test_row_replaced(self):
        r_yorkshire = et.Element("replace", attrib={"code": "Y"})
        create_subelement(r_yorkshire, "name", text="Greater Yorkshire")
        with database_session():
            _replace(models.Region, r_yorkshire)

        regions = models.Region.query.all()
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0].name, "Greater Yorkshire")

    def test_row_replaced_incorrect_value(self):
        r_yorkshire = et.Element("replace", attrib={"code": "Y"})
        create_subelement(r_yorkshire, "name",
                          attrib={"old": "Greater Yorkshire"},
                          text="Lesser Yorkshire")

        with database_session(), self.assertLogs("populate.modify") as log:
            _replace(models.Region, r_yorkshire)

        self.assertIn("Region.name: 'Greater Yorkshire' for {'code': 'Y'} "
                      "does not match {'Yorkshire'}.", log.output[0])

    def test_row_replaced_value_exists(self):
        r_yorkshire = et.Element("replace", attrib={"code": "Y"})
        create_subelement(r_yorkshire, "name",
                          attrib={"old": "Greater Yorkshire"},
                          text="Yorkshire")

        with database_session(), self.assertLogs("populate.modify") as log:
            _replace(models.Region, r_yorkshire)

        self.assertIn("Region.name: 'Yorkshire' for {'code': 'Y'} already "
                      "matches.", log.output[0])

    def test_row_replaced_no_match(self):
        r_london = et.Element("replace", attrib={"code": "L"})
        create_subelement(r_london, "name", attrib={"old": "London"},
                          text="Greater London")

        with database_session(), self.assertLogs("populate.modify") as log:
            _replace(models.Region, r_london)

        self.assertIn("No rows matching {'code': 'L'} for model 'Region'",
                      log.output[0])


class ModifyDataTests(utils.BaseAppTests):
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
        modify_data(xml_data)
        regions = models.Region.query.all()
        self.assertEqual(len(regions), 1)
        self.assertEqual([regions[0].code, regions[0].name],
                         ["L", "Greater London"])

    def test_modify_data_no_model(self):
        self.data = self.data.replace(b' model="Region"', b"")
        xml_data = io.BytesIO(self.data)
        with self.assertRaisesRegex(ValueError, "Every <table> element"):
            modify_data(xml_data)

    def test_modify_data_incorrect_model(self):
        self.data = self.data.replace(b'model="Region"', b'model="SomeTable"')
        xml_data = io.BytesIO(self.data)
        with self.assertRaisesRegex(ValueError, "Every <table> element"):
            modify_data(xml_data)