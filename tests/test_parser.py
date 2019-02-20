"""
Tests for search queries.
"""
import pytest

from nextbus import parser
from nextbus.parser import _fix_parentheses


@pytest.mark.parametrize("string, expected", [
    ("There are no parentheses.", "There are no parentheses."),
    ("(This is a (parenthesis).)", "(This is a (parenthesis).)"),
    ("(This is a (parenthesis).", "(This is a (parenthesis).)"),
    ("This is a (parenthesis).)", "This is a (parenthesis)."),
    (")This is a (parenthesis).(", "This is a (parenthesis).")
])
def test_parentheses(string, expected):
    assert _fix_parentheses(string) == expected


@pytest.fixture
def query_parser():
    return parser.create_tsquery_parser()


@pytest.mark.parametrize("query, expected", [
    ("(Trafalgar or Parliament) !(Square or Road)",
     "(Trafalgar|Parliament)&!(Square|Road)"),
    ("Great Titchfield Street and Oxford & Circus",
     "Great&Titchfield&Street&Oxford&Circus"),
    ("Trafalgar or Parliament | Leicester", "Trafalgar|Parliament|Leicester"),
    ("Parliament (not Road or !Square)", "Parliament&(!Road|!Square)"),
    ("Parliament not !Square", "Parliament&!!Square"),
    ("'Parliament Square' not Road", "Parliament<->Square&!Road"),
    ("\"Parliament and Square' or Road", "\"Parliament&Square'|Road"),
])
def test_parser(query_parser, query, expected):
    assert query_parser(query).to_string(defined=False) == expected


@pytest.mark.parametrize("query, expected", [
    ("Parliament and not (Square or Road) or Trafalgar",
     "Parliament|Trafalgar"),
])
def test_parser_defined(query_parser, query, expected):
    assert query_parser(query).to_string(defined=True) == expected


@pytest.mark.parametrize("query, expected", [
    ("Parliament and not Trafalgar", True),
    ("'Parliament Square'", True),
    ("not Trafalgar", False),
    ("not not Trafalgar", False),
    ("Parliament or not Trafalgar", False)
])
def test_check_tree(query_parser, query, expected):
    assert query_parser(query).check_tree() is expected


@pytest.mark.parametrize("query", [
    "not Trafalgar",
    "not not Trafalgar",
    "Parliament or not Trafalgar",
])
def test_parser_raises(query_parser, query):
    with pytest.raises(parser.SearchNotDefined):
        query_parser(query).to_string()


@pytest.mark.parametrize("query", [
    "<>",
    "北京市",
])
def test_wrong_characters(query):
    message = r"Query '.+' is too short or has invalid characters"
    with pytest.raises(parser.QueryTooShort, match=message):
        parser.validate_characters(query)


@pytest.mark.parametrize("query", [
    "Beijing",
    "Beijing 北京市",
    "München",
])
def test_mixed_characters(query):
    parser.validate_characters(query)
