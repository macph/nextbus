"""
Testing the extension functions for XSLT transformations and the element ->
dict function.
"""
import io
import unittest
import datetime

import lxml.etree as et

from nextbus import db, models
import nextbus.populate.utils as pop_utils
import utils


@pop_utils.xslt_text_func
def passthrough(_, *args):
    """ Simple function to pass through all arguments """
    return args


class ElementDictTests(unittest.TestCase):
    """ Testing the ``xml_as_dict`` function. """
    XML = """\
        <data>
            <a/>
            <b py_null="false"/>
            <c>Foo</c>
            <d py_type="bool">0</d>
            <e py_type="bool">true</e>
            <f py_type="int"/>
            <g py_type="int" py_null="false"/>
            <h py_type="int">512</h>
            <i py_type="float">0.5</i>
            <j py_type="datetime">2018-05-09T05:10:15</j>
        </data>
    """
    EXPECTED = {
        "a": None,
        "b": "",
        "c": "Foo",
        "d": False,
        "e": True,
        "f": None,
        "g": 0,
        "h": 512,
        "i": 0.5,
        "j": datetime.datetime(2018, 5, 9, 5, 10, 15)
    }

    def setUp(self):
        self.element = et.XML(self.XML)
        self.expected = self.EXPECTED.copy()

    def tearDown(self):
        del self.element, self.expected

    def test_element_to_dict(self):
        new_dict = pop_utils.xml_as_dict(self.element)
        self.assertEqual(new_dict, self.expected)

    def test_element_with_duration(self):
        sub = et.SubElement(self.element, "k")
        sub.set("py_type", "duration")
        sub.text = "PT5H5M5S"
        self.expected["k"] = datetime.timedelta(seconds=18305)

        new_dict = pop_utils.xml_as_dict(self.element)
        self.assertEqual(new_dict, self.expected)

    def test_element_multiple(self):
        et.SubElement(self.element, "i")

        with self.assertRaisesRegex(ValueError, "Multiple elements"):
            pop_utils.xml_as_dict(self.element)

    def test_element_invalid_type(self):
        sub = et.SubElement(self.element, "k")
        sub.set("py_type", "wrong_type")

        with self.assertRaisesRegex(ValueError, "Invalid py_type attribute"):
            pop_utils.xml_as_dict(self.element)

    def test_element_invalid_bool(self):
        sub = et.SubElement(self.element, "k")
        sub.set("py_type", "bool")
        sub.text = "Neither"

        with self.assertRaisesRegex(ValueError, "cannot be converted"):
            pop_utils.xml_as_dict(self.element)

    def test_element_cannot_convert(self):
        sub = et.SubElement(self.element, "k")
        sub.set("py_type", "int")
        sub.text = "foobar"

        with self.assertRaisesRegex(ValueError, "cannot be converted"):
            pop_utils.xml_as_dict(self.element)


class ElementTextTests(unittest.TestCase):
    """ Testing the ``xslt_text_func`` decorator which passes XPath queries
        in the form of lists of XML elements as text to the extension
        functions.
    """

    def test_function_registered(self):
        self.assertEqual(pop_utils.xslt_func["passthrough"], passthrough)

    def test_function_registered_new_name(self):
        @pop_utils.xslt_text_func("new_pt")
        def _passthrough(context, *args):
            return passthrough(context, *args)

        self.assertEqual(pop_utils.xslt_func["new_pt"], _passthrough)

    def test_decorator_one_element(self):
        result = [et.Element("name")]
        result[0].text = "text content"
        output = passthrough(None, result)
        self.assertEqual(output[0], "text content")

    def test_decorator_one_string(self):
        result = ["text content"]
        output = passthrough(None, result)
        self.assertEqual(output[0], "text content")

    def test_decorator_empty(self):
        result = []
        output = passthrough(None, result)
        self.assertEqual(output, (None,))

    def test_decorator_multiple_results(self):
        result = [et.Element("name"), "text content 2"]
        result[0].text = "text content 1"
        with self.assertRaises(ValueError):
            passthrough(None, result)

    def test_decorator_multiple_args(self):
        result_1 = [et.Element("name")]
        result_1[0].text = "text content 1"
        result_2 = [et.Element("name")]
        result_2[0].text = "text content 2"
        result_3 = "text content 3"

        output = passthrough(None, result_1, result_2, result_3)
        self.assertEqual(output, ("text content 1", "text content 2",
                                  "text content 3"))


class ExtensionTests(unittest.TestCase):
    """ Testing all XSLT extension methods populate utilities module. """
    def setUp(self):
        self.result = [et.Element("name")]

    def tearDown(self):
        del self.result

    def test_ext_replace_string(self):
        self.result[0].text = "Upper Warlingham"
        self.assertEqual(pop_utils.replace(None, self.result, "Warl", "Wold"),
                         "Upper Woldingham")

    def test_ext_upper_string(self):
        self.result[0].text = "East Grinstead"
        self.assertEqual(pop_utils.upper(None, self.result), "EAST GRINSTEAD")

    def test_ext_lower_string(self):
        self.result[0].text = "East Grinstead"
        self.assertEqual(pop_utils.lower(None, self.result), "east grinstead")

    def test_ext_capitalize_string(self):
        self.result[0].text = "St james's GATE (stop D)"
        self.assertEqual(pop_utils.capitalize(None, self.result),
                         "St James's Gate (Stop D)")

    def test_ext_left_split(self):
        self.result[0].text = "700|Amberline"
        self.assertEqual(pop_utils.l_split(None, self.result, "|"),
                         "700")

    def test_ext_right_split(self):
        self.result[0].text = "700|Amberline"
        self.assertEqual(pop_utils.r_split(None, self.result, "|"),
                         "Amberline")


class DurationTests(unittest.TestCase):
    """ Testing the duration converter """
    def test_one_second(self):
        delta = pop_utils.duration_delta("PT1S")
        self.assertEqual(delta.total_seconds(), 1)

    def test_one_second_zero_padding(self):
        delta = pop_utils.duration_delta("PT01S")
        self.assertEqual(delta.total_seconds(), 1)

    def test_half_second(self):
        delta = pop_utils.duration_delta("PT0.5S")
        self.assertEqual(delta.total_seconds(), 0.5)

    def test_minutes(self):
        delta = pop_utils.duration_delta("PT1M30S")
        self.assertEqual(delta.total_seconds(), 90)

    def test_hours(self):
        delta = pop_utils.duration_delta("PT1H60M60S")
        self.assertEqual(delta.total_seconds(), 7260)

    def test_days(self):
        delta = pop_utils.duration_delta("P6DT1H1M1S")
        self.assertEqual(delta.total_seconds(), 522061)

    def test_t_missing(self):
        with self.assertRaises(ValueError):
            pop_utils.duration_delta("P1H1M1S")

    def test_t_wrong_place(self):
        with self.assertRaises(ValueError):
            pop_utils.duration_delta("PT1D1M")

    def test_months(self):
        with self.assertRaises(ValueError):
            pop_utils.duration_delta("P1M1DT1H")

    def test_years(self):
        with self.assertRaises(ValueError):
            pop_utils.duration_delta("P1Y1D")


class AtcoCodeTests(utils.BaseAppTests):
    """ Test the retrieval of ATCO codes from the config """
    def test_default_codes(self):
        self.app.config["ATCO_CODES"] = None
        self.assertEqual(pop_utils.get_atco_codes(), None)

    def test_yorkshire_codes(self):
        self.app.config["ATCO_CODES"] = [370, 450]
        self.assertEqual(pop_utils.get_atco_codes(), [370, 450, 940])

    def test_invalid_type(self):
        self.app.config["ATCO_CODES"] = ["string", 370]
        with self.assertRaisesRegex(ValueError, "must be integers"):
            pop_utils.get_atco_codes()

    def test_invalid_string(self):
        self.app.config["ATCO_CODES"] = "string"
        with self.assertRaisesRegex(ValueError, "must be set to either"):
            pop_utils.get_atco_codes()


class EntryTests(utils.BaseAppTests):
    """ Tests on PopulateData without database commits """
    XML = (
        "<Data><Regions><Region><code>Y</code><name>Yorkshire</name>"
        "<modified>2006-01-25T07:54:31</modified></Region></Regions>"
        "</Data>"
    )
    XML_TWO = (
        "<Data><Regions><Region><code>NW</code><name>North West</name>"
        "<modified>2006-01-25T07:54:31</modified></Region><Region>"
        "<code>Y</code><name>Yorkshire</name>"
        "<modified>2006-01-25T07:54:31</modified></Region></Regions>"
        "</Data>"
    )
    EXPECTED = {
        "code": "Y",
        "name": "Yorkshire",
        "modified": "2006-01-25T07:54:31"
    }
    EXPECTED_DT = {
        "code": "Y",
        "name": "Yorkshire",
        "modified": "2006-01-25T07:54:31"
    }
    EXPECTED_NW = {
        "code": "NW",
        "name": "North West",
        "modified": "2006-01-25T07:54:31"
    }

    def setUp(self):
        with self.app.app_context():
            self.db_entries = pop_utils.PopulateData()
            self.db_entries.set_input(io.StringIO(self.XML))

    def tearDown(self):
        del self.db_entries

    def test_add_items(self):
        self.db_entries.add("Regions/Region", models.Region)
        self.assertEqual(self.db_entries.entries[models.Region][0],
                         self.EXPECTED)

    def test_add_multiple(self):
        self.db_entries.add("Regions/Region", models.Region)
        self.db_entries.add("Regions/Region", models.Region)
        self.assertEqual(self.db_entries.entries[models.Region],
                         [self.EXPECTED] * 2)


class EntryDBTests(utils.BaseAppTests):
    """ Tests on PopulateData and committing changes to database """
    xml = io.BytesIO(
        b"<Data><Regions><Region><code>Y</code><name>Yorkshire</name>"
        b"<modified/></Region></Regions></Data>"
    )

    def setUp(self):
        self.create_tables()
        # Set up temporary file to be read by et.parse()
        with self.app.app_context():
            self.db_entries = pop_utils.PopulateData()
            self.db_entries.set_input(self.xml)

    def tearDown(self):
        self.drop_tables()
        del self.db_entries

    def test_commit_changes(self):
        self.db_entries.add("Regions/Region", models.Region)
        self.db_entries.commit()
        # Query the DB
        region = models.Region.query.one()
        self.assertEqual((region.code, region.name), ("Y", "Yorkshire"))
