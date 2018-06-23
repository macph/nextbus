"""
Tests for search queries.
"""
import unittest

from nextbus import parser, search
from nextbus.parser import _fix_parentheses
import utils


class ParenthesisTests(unittest.TestCase):
    """ Tests for fixing opening and closing brackets in queries before passing
        to the parser.
    """
    def test_no_parentheses(self):
        string = "There are no parentheses."
        self.assertEqual(_fix_parentheses(string), string)

    def test_fix_parentheses_correct(self):
        string = "(This is a (parenthesis).)"
        self.assertEqual(_fix_parentheses(string), string)

    def test_fix_parentheses_left(self):
        self.assertEqual(_fix_parentheses("(This is a (parenthesis)."),
                         "(This is a (parenthesis).)")

    def test_fix_parentheses_right(self):
        self.assertEqual(_fix_parentheses("This is a (parenthesis).)"),
                         "This is a (parenthesis).")

    def test_fix_parentheses_flipped(self):
        self.assertEqual(_fix_parentheses(")This is a (parenthesis).("),
                         "This is a (parenthesis).")


class ParserTests(unittest.TestCase):
    """ Tests for the parser which parses search queries into TSQuery strings
        for searching the PSQL databases.
    """
    @classmethod
    def setUpClass(cls):
        cls.parser = staticmethod(parser.create_tsquery_parser())

    @classmethod
    def tearDownClass(cls):
        del cls.parser

    def test_words_parentheses(self):
        query = "(Trafalgar or Parliament) !(Square or Road)"
        expected = "(Trafalgar|Parliament)&!(Square|Road)"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(), expected)

    def test_words_and(self):
        query = "Great Titchfield Street and Oxford & Circus"
        expected = "Great&Titchfield&Street&Oxford&Circus"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(), expected)

    def test_words_or(self):
        query = "Trafalgar or Parliament | Leicester"
        expected = "Trafalgar|Parliament|Leicester"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(), expected)

    def test_words_not(self):
        query = "Parliament not Road or !Square"
        expected = "Parliament&!Road|!Square"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(), expected)

    def test_words_multiple_not(self):
        query = "Parliament not !Square"
        expected = "Parliament&!!Square"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(), expected)

    def test_words_exclude_not(self):
        query = "Parliament and not (Square or Road) or Trafalgar"
        expected = "Parliament|Trafalgar"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(defined=True), expected)

    def test_words_phrase(self):
        query = "'Parliament Square' not Road"
        expected = "Parliament<->Square&!Road"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(), expected)

    def test_words_broken_quotes(self):
        query = "\"Parliament and Square' or Road"
        expected = "\"Parliament&Square'|Road"
        parsed = self.parser(query)
        self.assertEqual(parsed.to_string(), expected)

    def test_words_is_defined_and(self):
        query = "Parliament and not Trafalgar"
        parsed = self.parser(query)
        parsed.to_string(defined=True)

    def test_words_is_defined_phrase(self):
        query = "'Parliament Square'"
        parsed = self.parser(query)
        parsed.to_string(defined=True)

    def test_words_not_defined(self):
        query = "not Trafalgar"
        parsed = self.parser(query)
        with self.assertRaisesRegex(parser.SearchNotDefined,
                                    "not defined enough"):
            parsed.to_string(defined=True)

    def test_words_not_defined_multiple(self):
        query = "not not Trafalgar"
        parsed = self.parser(query)
        with self.assertRaisesRegex(parser.SearchNotDefined,
                                    "not defined enough"):
            parsed.to_string(defined=True)

    def test_words_not_defined_or(self):
        query = "Parliament or not Trafalgar"
        parsed = self.parser(query)
        with self.assertRaisesRegex(parser.SearchNotDefined,
                                    "not defined enough"):
            parsed.to_string(defined=True)


class SearchCharacterValidationTests(unittest.TestCase):
    """ Tests for validating search queries. """
    def test_search_wrong_characters(self):
        msg = "Query '<>' is too short or has invalid characters"
        with self.assertRaisesRegex(search.QueryTooShort, msg):
            search.validate_characters("<>")

    def test_search_non_latin(self):
        msg = "Query '北京市' is too short or has invalid characters"
        with self.assertRaisesRegex(search.QueryTooShort, msg):
            search.validate_characters("北京市")

    def test_search_correct_non_latin(self):
        search.validate_characters("Beijing 北京市")

    def test_search_correct(self):
        search.validate_characters("Beijing")
