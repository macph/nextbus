"""
Testing the extension functions for XSLT transformations and the element ->
dict function.
"""
import lxml.etree as et
import psycopg2
import pytest

from nextbus import db, models
import nextbus.populate.utils as pop_utils


def test_xml_dict():
    xml = et.XML('<data><a/><b default="64"/><c default="128">256</c><d>512</d>'
                 '<e>1024</e></data>')
    expected = {"a": None, "b": "64", "c": "256", "d": "512", "e": "1024"}

    assert pop_utils.xml_as_dict(xml) == expected


def test_xml_dict_repeated():
    xml = et.XML("<data><a/><b>512</b><b>1024</b></data>")

    message = "Multiple elements have the same tag 'b'."
    with pytest.raises(ValueError, match=message):
        pop_utils.xml_as_dict(xml)


@pop_utils.xslt_text_func
def _pass_through(_, *args):
    """ Simple function to pass through all arguments """
    return args


def _element_text(tag, text):
    element = et.Element(tag)
    element.text = text

    return element


def test_func_is_registered():
    assert pop_utils.xslt_func["_pass_through"] == _pass_through


def test_func_new_name():
    @pop_utils.xslt_text_func("new_pass_through")
    def pass_through(_, *args):
        return args

    assert pop_utils.xslt_func["new_pass_through"] == pass_through


def test_decorator_one_element():
    assert _pass_through(None, [_element_text("name", "text")]) == ("text",)


def test_decorator_one_string():
    assert _pass_through(None, ["text"]) == ("text",)


def test_decorator_empty():
    assert _pass_through(None, []) == (None,)


def test_decorator_multiple_results():
    with pytest.raises(ValueError):
        _pass_through(None, [_element_text("name", "text 1"), "text 2"])


def test_decorator_multiple_args():
    args = ([_element_text("name", "text 1")],
            [_element_text("name", "text 2")],
            "text 3")
    assert _pass_through(None, *args) == ("text 1", "text 2", "text 3")


def test_ext_replace_string():
    elem = _element_text("name", "Upper Warlingham")
    assert pop_utils.replace(None, [elem], "Warl", "Wold") == "Upper Woldingham"


def test_ext_upper():
    elem = _element_text("name", "East Grinstead")
    assert pop_utils.upper(None, [elem]) == "EAST GRINSTEAD"


def test_ext_lower():
    elem = _element_text("name", "East Grinstead")
    assert pop_utils.lower(None, [elem]) == "east grinstead"


def test_ext_capitalize_empty():
    elem = _element_text("name", "")
    assert pop_utils.capitalize(None, [elem]) == ""


def test_ext_capitalize():
    elem = _element_text("name", "St james's GATE (stop D)")
    assert pop_utils.capitalize(None, [elem]) == "St James's Gate (Stop D)"


def test_ext_left_split():
    elem = _element_text("name", "700|Amberline")
    assert pop_utils.l_split(None, [elem], "|") == "700"


def test_ext_right_split():
    elem = _element_text("name", "700|Amberline")
    assert pop_utils.r_split(None, [elem], "|") == "Amberline"


XML = b"<Data><Region><code>Y</code><name>Yorkshire</name></Region></Data>"
XML_TWO = (b"<Data><Region><code>NW</code><name>North West</name></Region>"
           b"<Region><code>Y</code><name>Yorkshire</name></Region></Data>")

EXPECTED_NW = {"code": "NW", "name": "North West"}
EXPECTED_Y = {"code": "Y", "name": "Yorkshire"}


def test_collect_items(with_app):
    data = pop_utils.collect_xml_data(et.ElementTree(et.fromstring(XML_TWO)))
    assert data == {models.Region: [EXPECTED_NW, EXPECTED_Y]}


EXISTING = [("GB", "Great Britain"), ("L", "Greater London")]
EXPECTED = [("NW", "North West"), ("Y", "Yorkshire")]


def test_commit_data(load_db):
    with db.engine.begin() as connection:
        pop_utils.populate_database(
            connection,
            {models.Region: [EXPECTED_NW, EXPECTED_Y]},
            delete=False
        )

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == EXISTING + EXPECTED


def test_commit_data_overwrite(load_db):
    l_modified = {"code": "L", "name": "London"}
    with db.engine.begin() as connection:
        pop_utils.populate_database(
            connection,
            {models.Region: [l_modified]},
            overwrite=True
        )

    regions = models.Region.query.order_by("code").all()
    expected = [EXISTING[0], ("L", "London")]
    assert [(r.code, r.name) for r in regions] == expected


def test_commit_data_delete(load_db):
    with db.engine.begin() as connection:
        pop_utils.populate_database(
            connection,
            {models.Region: [EXPECTED_NW, EXPECTED_Y]},
            delete=True
        )

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == EXPECTED


def test_commit_data_delete_excluded(load_db):
    with db.engine.begin() as connection:
        pop_utils.populate_database(
            connection,
            {models.Region: [EXPECTED_NW, EXPECTED_Y]},
            delete=True,
            exclude=[models.Region]
        )

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == EXISTING + EXPECTED


def test_commit_data_truncate_cascade(load_db):
    with db.engine.begin() as connection:
        pop_utils.truncate(connection, models.Region.__table__)

    regions = models.Region.query.order_by("code").all()
    assert not regions


def test_commit_data_truncate_no_cascade(load_db):
    message = "cannot truncate a table referenced in a foreign key constraint"
    with db.engine.begin() as connection, \
            pytest.raises(psycopg2.NotSupportedError, match=message):
        pop_utils.truncate(connection, models.Region.__table__, cascade=False)

    regions = models.Region.query.order_by("code").all()
    assert regions
