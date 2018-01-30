"""
Testing the extension functions for XSLT transformations and the element ->
dict function.
"""
import unittest
import lxml.etree as et

from nextbus.populate.naptan import (_element_as_dict, _element_text,
                                     _ExtFunctions)

class ElementDictTests(unittest.TestCase):
    """ Testing the ``_element_as_dict`` function. """

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
        new_dict = _element_as_dict(self.element)
        self.assertEqual(new_dict, self.expected)

    def test_element_upper(self):
        upper = lambda s: s.upper()
        new_dict = _element_as_dict(self.element, tag5=upper)
        self.expected["tag5"] = self.expected["tag5"].upper()
        self.assertEqual(new_dict, self.expected)

    def test_element_wrong_key(self):
        upper = lambda s: s.upper()
        with self.assertRaises(ValueError):
            new_dict = _element_as_dict(self.element, tag10=upper)

    def test_element_wrong_function(self):
        replace = lambda s, o, n: s.replace(o, n)
        with self.assertRaisesRegex(TypeError, "only one argument"):
            new_dict = _element_as_dict(self.element, tag5=replace)


class ElementTextTests(unittest.TestCase):
    """ Testing the ``_element_text`` decorator which passes XPath queries
        in the form of lists of XML elements as text to the extension
        functions.
    """

    @staticmethod
    @_element_text
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
            output = self.passthrough(None, None, result)


class ExtensionTests(unittest.TestCase):
    """ Testing all methonds in the ``_ExtFunctions`` class. """

    def setUp(self):
        self.ext = _ExtFunctions()
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
