"""
Testing the populate module.
"""
import os
import tempfile
import unittest
import lxml.etree as et

from nextbus.pop import _XPath

HOME_DIR = os.path.dirname(os.path.realpath(__file__))

class XPathTests(unittest.TestCase):
    """ Tests the _XPath helper class. """
    def setUp(self):
        self.data = et.parse(os.path.join(HOME_DIR, "NaPTAN_example.xml"))
        self.xp = _XPath(self.data, 'n')

    def tearDown(self):
        del self.data
        del self.xp

    def test_namespace(self):
        self.assertEqual(self.xp.namespace['n'], "http://www.naptan.org.uk/")

    def test_query(self):
        nodes = self.xp("n:StopPoints/n:StopPoint")
        self.assertEqual(len(nodes), 2)

    def test_text(self):
        atco_code = "370023697"
        text = self.xp.text("n:StopPoints/n:StopPoint[n:AtcoCode='%s']/n:AtcoCode"
                            % atco_code)
        self.assertEqual(text, atco_code)

    def test_text_attribute(self):
        atco_code = "370023697"
        text = self.xp.text("n:StopPoints/n:StopPoint[n:AtcoCode='%s']/@Status"
                            % atco_code)

        self.assertEqual(text, "active")

    def test_subelement_text(self):
        atco_code = "370023697"
        node = self.xp("n:StopPoints/n:StopPoint[n:AtcoCode='%s']" % atco_code)[0]
        text = self.xp.text("n:AtcoCode", element=node)
        self.assertEqual(text, atco_code)
    
    def test_text_not_found(self):
        with self.assertRaisesRegex(ValueError, "No elements") as are:
            text = self.xp.text("n:Locality")
    
    def test_multiple_text(self):
        with self.assertRaisesRegex(ValueError, "Multiple elements") as are:
            text = self.xp.text("n:StopPoints/n:StopPoint")

    def test_iter_list(self):
        nodes = self.xp("n:StopPoints/n:StopPoint")
        output = self.xp.iter_text("n:AtcoCode", nodes)

        expected = ["370020362", "370023697"]
        self.assertListEqual(output, expected)

    def test_dict(self):
        atco_code = "370023697"
        node = self.xp("n:StopPoints/n:StopPoint[n:AtcoCode='%s']" % atco_code)[0]
        ls = {"naptan_code": "n:NaptanCode", "name": "n:Descriptor/n:ShortCommonName"}
        output = self.xp.dict_text(ls, element=node)

        expected = {"naptan_code": "37023697", "name": "City Hall CH3"}
        self.assertDictEqual(output, expected)

    def test_dict_missing(self):
        atco_code = "370020362"
        node = self.xp("n:StopPoints/n:StopPoint[n:AtcoCode='%s']" % atco_code)[0]
        ls = {"naptan_code": "n:NaptanCode",
              "name": "n:AlternativeDescriptors/n:Descriptor/n:ShortCommonName"}
        output = self.xp.dict_text(ls, element=node)

        expected = {"naptan_code": "37020362", "name": None}
        self.assertDictEqual(output, expected)
