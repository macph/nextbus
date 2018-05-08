"""
Testing the extension functions for XSLT transformations and the element ->
dict function.
"""
import datetime
import io
import unittest

import lxml.etree as et

from nextbus import db, models
from nextbus.populate import (DBEntries, ext_function_text, get_atco_codes,
                              merge_xml, xml_as_dict, XSLTExtFunctions)
import utils


XML_FIRST = io.BytesIO(b"""\
<root xmlns="some/namespace">
  <first>
    <sub><a>1</a><b>2</b><c>3</c></sub>
    <sub><a>4</a><b>5</b><c>6</c></sub>
  </first>
</root>
""")

XML_SECOND = io.BytesIO(b"""\
<root xmlns="some/namespace">
  <first>
    <sub><a>7</a><b>8</b><c>9</c></sub>
  </first>
  <second>
    <child><d>10</d><e>11</e><f>12</f></child>
  </second>
</root>
""")

XML_THIRD = io.BytesIO(b"""\
<root xmlns="some/namespace">
  <second>
    <child><d>13</d><e>14</e><f>15</f></child>
  </second>
</root>
""")

XML_EXPECTED = io.BytesIO(b"""\
<root xmlns="some/namespace">
  <first>
    <sub><a>1</a><b>2</b><c>3</c></sub>
    <sub><a>4</a><b>5</b><c>6</c></sub>
    <sub><a>7</a><b>8</b><c>9</c></sub>
  </first>
  <second>
    <child><d>10</d><e>11</e><f>12</f></child>
    <child><d>13</d><e>14</e><f>15</f></child>
  </second>
</root>
""")

XML_WRONG_ROOT = io.BytesIO(b"""\
<data xmlns="some/namespace">
  <first>
    <sub><a>7</a><b>8</b><c>9</c></sub>
  </first>
</data>
""")

XML_WRONG_NAMESPACE = io.BytesIO(b"""\
<root xmlns="other/namespace">
  <first>
    <sub><a>7</a><b>8</b><c>9</c></sub>
  </first>
</root>
""")


class MergeXMLTests(utils.BaseXMLTests):
    """ Testing the ``merge_xml`` function. """
    def test_correct_merge(self):
        merged = merge_xml(iter([XML_FIRST, XML_SECOND, XML_THIRD]),
                           parser=self.parser)
        expected = et.parse(XML_EXPECTED, parser=self.parser)
        self.assertXMLElementsEqual(merged.getroot(), expected.getroot())

    def test_wrong_root(self):
        with self.assertRaisesRegex(ValueError, "same root or namespace"):
            merge_xml(iter([XML_FIRST, XML_WRONG_ROOT]))

    def test_wrong_namespace(self):
        with self.assertRaisesRegex(ValueError, "same root or namespace"):
            merge_xml(iter([XML_FIRST, XML_WRONG_NAMESPACE]))


class ElementDictTests(unittest.TestCase):
    """ Testing the ``xml_as_dict`` function. """
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
        new_dict = xml_as_dict(self.element)
        self.assertEqual(new_dict, self.expected)


class ElementTextTests(unittest.TestCase):
    """ Testing the ``_element_text`` decorator which passes XPath queries
        in the form of lists of XML elements as text to the extension
        functions.
    """
    @staticmethod
    @ext_function_text
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
            self.passthrough(None, None, result)


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


class AtcoCodeTests(utils.BaseAppTests):
    """ Test the retrieval of ATCO codes from the config """
    def test_default_codes(self):
        self.app.config["ATCO_CODES"] = "all"
        self.assertEqual(get_atco_codes(), None)

    def test_yorkshire_codes(self):
        self.app.config["ATCO_CODES"] = [370, 450]
        self.assertEqual(get_atco_codes(), [370, 450, 940])
    
    def test_invalid_type(self):
        self.app.config["ATCO_CODES"] = ["string", 370]
        with self.assertRaisesRegex(ValueError, "must be integers"):
            get_atco_codes()

    def test_invalid_string(self):
        self.app.config["ATCO_CODES"] = "string"
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
        "modified": "2006-01-25T07:54:31"
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
        def func(item):
            item["name"] = item["name"].upper()
            return item

        self.db_entries.add("Regions/Region", models.Region, func=func)
        region = {
            "code": "Y",
            "name": "YORKSHIRE",
            "modified": "2006-01-25T07:54:31"
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
        def func(item, _):
            return item
        with self.assertRaisesRegex(TypeError, "the only argument"):
            self.db_entries.add("Regions/Region", models.Region, func=func)


class EntryDBTests(utils.BaseAppTests):
    """ Tests on _DBEntries and committing changes to database """
    xml = io.BytesIO(
        b"<Data><Regions><Region><code>Y</code><name>Yorkshire</name>"
        b"<modified/></Region></Regions></Data>"
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
        insert = self.db_entries._create_insert_statement(models.Region)
        # Add binding to engine
        insert.bind = db.engine
        statement = str(insert)
        self.assertRegex(
            statement,
            r"INSERT INTO region \(code, name, modified\) VALUES"
        )
        self.assertNotRegex(statement, r"ON CONFLICT.+?DO UPDATE")

    def test_insert_statement_column(self):
        self.db_entries.add("Regions/Region", models.Region, indices=("code",))
        insert = self.db_entries._create_insert_statement(models.Region)
        # Bind statement to database engine
        insert.bind = db.engine
        statement = str(insert)
        self.assertRegex(
            statement,
            r"INSERT INTO region \(code, name, modified\) "
            r"VALUES \(.+?\) ON CONFLICT \(code\) "
            r"DO UPDATE SET code = excluded.code, name = excluded.name, "
            r"modified = excluded.modified WHERE region.modified < "
            r"excluded.modified"
        )

    def test_commit_changes(self):
        self.db_entries.add("Regions/Region", models.Region)
        self.db_entries.commit()
        # Query the DB
        region = models.Region.query.one()
        self.assertEqual((region.code, region.name), ("Y", "Yorkshire"))
