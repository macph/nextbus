"""
Testing the extension functions for XSLT transformations and the element ->
dict function.
"""
import io
import unittest
import datetime

import dateutil.parser as dp
import lxml.etree as et

from nextbus import db, models
import nextbus.populate.utils as pop_utils
import utils

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
        new_dict = pop_utils.xml_as_dict(self.element)
        self.assertEqual(new_dict, self.expected)


class ElementTextTests(unittest.TestCase):
    """ Testing the ``_element_text`` decorator which passes XPath queries
        in the form of lists of XML elements as text to the extension
        functions.
    """
    @staticmethod
    @pop_utils.ext_function_text
    def passthrough(context, result, *args, **kwargs):
        """ Simple function to pass through all arguments """
        return context, result, args, kwargs

    def test_decorator_one_element(self):
        result = [et.Element("name")]
        result[0].text = "text content"
        output = self.passthrough(None, result)
        self.assertEqual(output[1], "text content")

    def test_decorator_one_string(self):
        result = ["text content"]
        output = self.passthrough(None, result)
        self.assertEqual(output[1], "text content")

    def test_decorator_empty(self):
        result = []
        output = self.passthrough(None, result)
        self.assertEqual(output, None)

    def test_decorator_multiple(self):
        result = [et.Element("name"), "text content 2"]
        result[0].text = "text content 1"
        with self.assertRaises(ValueError):
            self.passthrough(None, result)


class ExtensionTests(unittest.TestCase):
    """ Testing all methonds in the ``_ExtFunctions`` class. """
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


class DayWeekTests(unittest.TestCase):
    """ Testing the days_week extension function. """
    ns = "{http://some_namespace/}"

    def setUp(self):
        self.node = et.Element(self.ns + "RegularDayType")
        self.nodes = [self.node]
        self.days = et.Element(self.ns + "DaysOfWeek")

    def tearDown(self):
        del self.node, self.nodes

    def test_holidays(self):
        et.SubElement(self.node, self.ns + "HolidaysOnly")

        self.assertEqual(pop_utils.days_week(None, self.nodes), 0)

    def test_full_week(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "MondayToSunday")

        self.assertEqual(pop_utils.days_week(None, self.nodes), 254)

    def test_weekend(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "Weekend")

        self.assertEqual(pop_utils.days_week(None, self.nodes), 192)

    def test_not_saturday(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "Sunday")
        et.SubElement(self.days, self.ns + "NotSaturday")

        self.assertEqual(pop_utils.days_week(None, self.nodes), 190)

    def test_not_sunday(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "MondayToSaturday")

        self.assertEqual(pop_utils.days_week(None, self.nodes), 126)

    def test_mon_wed_fri(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "Monday")
        et.SubElement(self.days, self.ns + "Wednesday")
        et.SubElement(self.days, self.ns + "Friday")

        self.assertEqual(pop_utils.days_week(None, self.nodes), 42)


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
        print(delta)
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


class EntryTests(unittest.TestCase):
    """ Tests on _DBEntries without database commits """
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
        "modified": datetime.datetime(2006, 1, 25, 7, 54, 31)
    }
    EXPECTED_NW = {
        "code": "NW",
        "name": "North West",
        "modified": datetime.datetime(2006, 1, 25, 7, 54, 31)
    }

    @staticmethod
    def _add_modified_date(row):
        row["modified"] = dp.parse(row["modified"])
        return row

    def setUp(self):
        self.db_entries = pop_utils.DBEntries(io.StringIO(self.XML))

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

    def test_add_items_func(self):
        self.db_entries.add("Regions/Region", models.Region,
                            func=self._add_modified_date)
        self.assertEqual(self.db_entries.entries[models.Region][0],
                         self.EXPECTED_DT)

    def test_add_item_wrong_function(self):
        def func(item, _):
            return item
        with self.assertRaisesRegex(TypeError, "the only argument"):
            self.db_entries.add("Regions/Region", models.Region, func=func)

    def test_no_duplicate(self):
        self.db_entries.set_data(io.StringIO(self.XML_TWO))
        self.db_entries.add("Regions/Region", models.Region, indices=("code",),
                            func=self._add_modified_date)
        print(self.db_entries.entries)
        self.db_entries._check_duplicates()
        self.assertEqual(self.db_entries.entries[models.Region],
                         [self.EXPECTED_NW, self.EXPECTED_DT])

    def test_remove_duplicate(self):
        self.db_entries.set_data(io.StringIO(self.XML))
        self.db_entries.add("Regions/Region", models.Region, indices=("code",),
                            func=self._add_modified_date)
        self.db_entries.add("Regions/Region", models.Region, indices=("code",),
                            func=self._add_modified_date)
        self.db_entries._check_duplicates()
        self.assertEqual(len(self.db_entries.entries[models.Region]), 1)
        self.assertEqual(self.db_entries.entries[models.Region][0],
                         self.EXPECTED_DT)


class EntryDBTests(utils.BaseAppTests):
    """ Tests on _DBEntries and committing changes to database """
    xml = io.BytesIO(
        b"<Data><Regions><Region><code>Y</code><name>Yorkshire</name>"
        b"<modified/></Region></Regions></Data>"
    )

    def setUp(self):
        self.create_tables()
        # Set up temporary file to be read by et.parse()
        self.db_entries = pop_utils.DBEntries(self.xml)

    def tearDown(self):
        self.drop_tables()
        del self.db_entries

    def test_commit_changes(self):
        self.db_entries.add("Regions/Region", models.Region)
        self.db_entries.commit()
        # Query the DB
        region = models.Region.query.one()
        self.assertEqual((region.code, region.name), ("Y", "Yorkshire"))
