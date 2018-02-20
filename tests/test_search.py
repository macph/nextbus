"""
Tests for search queries.
"""
import unittest

from nextbus import parser
from nextbus.parser import _fix_parentheses


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
    """ Tests for the parser which converts search queries into TSQuery strings
        for searching the PSQL databases.
    """

    @classmethod
    def setUpClass(cls):
        cls.parser = parser.TSQueryParser()

    @classmethod
    def tearDownClass(cls):
        del cls.parser

    def test_words_parentheses(self):
        query = "(Trafalgar or Parliament) !(Square or Road)"
        expected = "(Trafalgar|Parliament)&!(Square|Road)"
        self.assertEqual(self.parser(query), expected)

    def test_words_and(self):
        query = "Great Titchfield Street and Oxford & Circus"
        expected = "Great&Titchfield&Street&Oxford&Circus"
        self.assertEqual(self.parser(query), expected)

    def test_words_or(self):
        self.assertEqual(self.parser("Trafalgar or Parliament | Leicester"),
                         "Trafalgar|Parliament|Leicester")

    def test_words_not(self):
        self.assertEqual(self.parser("!Parliament not Road"),
                         "!Parliament&!Road")
