"""
Tests for search queries.
"""
import unittest

from nextbus import parser
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


class ParserTests(utils.BaseAppTests):
    """ Tests for the parser which parses search queries into TSQuery strings
        for searching the PSQL databases.
    """

    @classmethod
    def setUpClass(cls):
        super(ParserTests, cls).setUpClass()
        cls.parser = parser.TSQueryParser()

    @classmethod
    def tearDownClass(cls):
        del cls.parser
        super(ParserTests, cls).tearDownClass()

    def test_words_parentheses(self):
        query = "(Trafalgar or Parliament) !(Square or Road)"
        expected = ("(Trafalgar|Parliament)&!(Square|Road)",
                    "(Trafalgar|Parliament)")
        self.assertEqual(self.parser.parse(query), expected)

    def test_words_and(self):
        query = "Great Titchfield Street and Oxford & Circus"
        expected = "Great&Titchfield&Street&Oxford&Circus"
        self.assertEqual(self.parser.parse(query), (expected, expected))

    def test_words_or(self):
        query = "Trafalgar or Parliament | Leicester"
        expected = "Trafalgar|Parliament|Leicester"
        self.assertEqual(self.parser.parse(query), (expected, expected))

    def test_words_not(self):
        query = "Parliament not Road or !Square"
        expected = ("Parliament&!Road|!Square", "Parliament")
        self.assertEqual(self.parser.parse(query), expected)

    def test_words_phrase(self):
        query = "'Parliament Square' not Road"
        expected = ("Parliament<->Square&!Road", "Parliament<->Square")
        self.assertEqual(self.parser.parse(query), expected)

    def test_words_broken_quotes(self):
        query = "\"Parliament and Square' or Road"
        expected = "\"Parliament&Square'|Road"
        self.assertEqual(self.parser.parse(query), (expected, expected))
