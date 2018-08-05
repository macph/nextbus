"""
Testing TNDS population.
"""
import os
import unittest

import lxml.etree as et

from nextbus.populate.utils import xslt_func
from nextbus.populate.tnds import _get_tnds_transform, days_week, RowIds
import utils


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
TNDS_OUT = os.path.join(TEST_DIR, "TNDS_output.xml")
TNDS_RAW = os.path.join(TEST_DIR, "TNDS_raw.xml")


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

        self.assertEqual(days_week(None, self.nodes), 0)

    def test_full_week(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "MondayToSunday")

        self.assertEqual(days_week(None, self.nodes), 254)

    def test_weekend(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "Weekend")

        self.assertEqual(days_week(None, self.nodes), 192)

    def test_not_saturday(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "Sunday")
        et.SubElement(self.days, self.ns + "NotSaturday")

        self.assertEqual(days_week(None, self.nodes), 190)

    def test_not_sunday(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "MondayToSaturday")

        self.assertEqual(days_week(None, self.nodes), 126)

    def test_mon_wed_fri(self):
        self.node.append(self.days)
        et.SubElement(self.days, self.ns + "Monday")
        et.SubElement(self.days, self.ns + "Wednesday")
        et.SubElement(self.days, self.ns + "Friday")

        self.assertEqual(days_week(None, self.nodes), 42)


class TransformTests(utils.BaseXMLTests):
    """ Testing TNDS XSLT functions. """
    def test_transform_tnds(self):
        transform = _get_tnds_transform()
        expected = et.parse(TNDS_OUT, parser=self.parser)
        # Set up functions to assign IDs
        RowIds(check_existing=False)

        def always_true(_, *args):
            return True

        # Replicate functions which check for existing stops and operators
        xslt_func["national_op_new"] = always_true
        xslt_func["local_op_new"] = always_true
        xslt_func["stop_exists"] = always_true

        try:
            output = transform(et.parse(TNDS_RAW), region=et.XSLT.strparam("Y"),
                               file=et.XSLT.strparam("TNDS_raw.xml"))
        except (et.XSLTApplyError, et.XSLTParseError) as err:
            for msg in getattr(err, "error_log"):
                print(msg)
            raise

        self.assertXMLElementsEqual(expected.getroot(), output.getroot())
