"""
Testing TNDS population.
"""
import os

import lxml.etree as et

from nextbus.populate.tnds import _get_tnds_transform
import utils


TEST_DIR = os.path.dirname(os.path.realpath(__file__))
TNDS_OUT = os.path.join(TEST_DIR, "TNDS_output.xml")
TNDS_RAW = os.path.join(TEST_DIR, "TNDS_raw.xml")


class TransformTests(utils.BaseXMLTests):
    """ Testing TNDS XSLT functions. """
    def test_transform_tnds(self):
        transform = _get_tnds_transform()
        expected = et.parse(TNDS_OUT, parser=self.parser)

        try:
            output = transform(et.parse(TNDS_RAW), region=et.XSLT.strparam("Y"))
        except (et.XSLTApplyError, et.XSLTParseError) as err:
            for msg in getattr(err, "error_log"):
                print(msg)
            raise

        self.assertXMLElementsEqual(output.getroot(), expected.getroot())
