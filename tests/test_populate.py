"""
Testing the populate module.
"""
import os
import tempfile
import unittest
import lxml.etree as et

from nextbus.populate import IterChunk, XPath

HOME_DIR = os.path.dirname(os.path.realpath(__file__))


class XPathTests(unittest.TestCase):
    """ Tests the XPath helper class. """
    def setUp(self):
        self.data = et.parse(os.path.join(HOME_DIR, "NaPTAN_example.xml"))
        self.xp = XPath(self.data, 'n')

    def tearDown(self):
        del self.data
        del self.xp

    def test_namespace(self):
        self.assertEqual(self.xp.namespace['n'], "http://www.naptan.org.uk/")

    def test_query(self):
        nodes = self.xp("n:StopPoints/n:StopPoint")
        self.assertEqual(len(nodes), 2)

    def test_query_no_prefix(self):
        nodes = self.xp("StopPoints/StopPoint")
        self.assertEqual(len(nodes), 2)

    def test_text(self):
        atco_code = "370023697"
        text = self.xp.text("n:StopPoints/n:StopPoint[n:AtcoCode='%s' or AtcoCode='496346433']/n:AtcoCode"
                            % atco_code)
        self.assertEqual(text, atco_code)

    def test_text_no_prefix(self):
        atco_code = "370023697"
        text = self.xp.text("StopPoints/StopPoint[AtcoCode='%s' or AtcoCode='496346433']/AtcoCode"
                            % atco_code)
        self.assertEqual(text, atco_code)

    def test_text_attribute(self):
        atco_code = "370023697"
        text = self.xp.text("StopPoints/StopPoint[AtcoCode='%s']/@Status"
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

    def test_over_list(self):
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

    def test_dict_no_prefix(self):
        atco_code = "370023697"
        node = self.xp("n:StopPoints/n:StopPoint[n:AtcoCode='%s']" % atco_code)[0]
        ls = {"naptan_code": "NaptanCode", "name": "Descriptor/ShortCommonName"}
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


class IterChunkTests(unittest.TestCase):

    def setUp(self):
        self.range = iter(range(500))
        self.iter = IterChunk(self.range, 100)

    def tearDown(self):
        del self.range
        del self.iter

    def test_iter_mid(self):
        next(self.iter)
        next(self.iter)
        self.assertListEqual(next(self.iter), list(range(200, 300)))

    def test_iter_loop(self):
        new_list = []
        for chunk in self.iter:
            new_list.extend(chunk)
        self.assertListEqual(new_list, list(range(500)))

    def test_iter_larger(self):
        chunks = IterChunk(self.range, 600)
        self.assertListEqual(next(chunks), list(range(500)))
