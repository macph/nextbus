"""
Testing the modification functions for processing populated data.
"""
import logging
import io

import lxml.etree as et
import pytest

from nextbus import models
from nextbus.populate.utils import database_session
from nextbus.populate.modify import (_create_row, _delete_row, _replace_row,
                                     modify_data)


LOGGER = "nextbus.populate.modify"
MODIFY_XML = b"""\
<data>
  <table model="Region">
    <create>
      <code>S</code>
      <name>Scotland</name>
      <modified>2006-01-25T07:54:31</modified>
    </create>
    <create>
      <code>Y</code>
      <name>Yorkshire</name>
      <modified>2006-01-25T07:54:31</modified>
    </create>
  </table>
  <table model="Region">
    <replace code="L">
      <name old="Greater London">London</name>
    </replace>
    <delete code="GB"/>
  </table>
</data>
"""


def test_rows_added(load_db):
    yorkshire = et.XML("<create><code>Y</code><name>Yorkshire</name></create>")
    scotland = et.XML("<create><code>S</code><name>Scotland</name></create>")

    with database_session():
        _create_row(models.Region, scotland)
        _create_row(models.Region, yorkshire)

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == [
        ("GB", "Great Britain"), ("L", "Greater London"), ("S", "Scotland"),
        ("Y", "Yorkshire")
    ]


def test_rows_add_empty():
    empty = et.XML("<create/>")

    with pytest.raises(ValueError, match="Each <create> element requires"):
        _create_row(models.Region, empty)


def test_rows_deleted(load_db):
    gb = et.XML('<delete code="GB"/>')

    with database_session():
        _delete_row(models.Region, gb)

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == [("L", "Greater London")]


def test_rows_deleted_no_attr():
    empty = et.XML('<delete/>')

    with pytest.raises(ValueError, match="Each <delete> element requires"):
        _delete_row(models.Region, empty)


def test_rows_deleted_no_match(load_db, caplog):
    yorkshire = et.XML('<delete code="Y"/>')

    with database_session():
        _delete_row(models.Region, yorkshire)

    log = (LOGGER, logging.WARNING,
           "Region: No rows matching {'code': 'Y'} found.")
    assert log in caplog.record_tuples

    regions = models.Region.query.order_by("code").all()
    assert [r.code for r in regions] == ["GB", "L"]


def test_rows_replaced(load_db, caplog):
    london = et.XML('<replace code="L">'
                    '<name old="Greater London">The Metropolis</name>'
                    '</replace>')

    with database_session():
        _replace_row(models.Region, london)

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == [("GB", "Great Britain"),
                                                   ("L", "The Metropolis")]


def test_rows_replaced_no_attr():
    london = et.XML('<replace>'
                    '<name old="Greater London">The Metropolis</name>'
                    '</replace>')

    with pytest.raises(ValueError, match="Each <replace> element requires"):
        _replace_row(models.Region, london)


def test_row_replaced_incorrect_value(load_db, caplog):
    london = et.XML('<replace code="L">'
                    '<name old="London">The Metropolis</name>'
                    '</replace>')

    with database_session():
        _replace_row(models.Region, london)

    log = (LOGGER, logging.WARNING,
           "Region: name 'London' for {'code': 'L'} does not match existing "
           "value 'Greater London'.")
    assert log in caplog.record_tuples

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == [("GB", "Great Britain"),
                                                   ("L", "The Metropolis")]


def test_row_replaced_same_value(load_db, caplog):
    london = et.XML('<replace code="L">'
                    '<name old="London">Greater London</name>'
                    '</replace>')

    with database_session():
        _replace_row(models.Region, london)

    log = (LOGGER, logging.WARNING,
           "Region: name 'Greater London' for {'code': 'L'} already matches.")
    assert log in caplog.record_tuples

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == [("GB", "Great Britain"),
                                                   ("L", "Greater London")]


def test_row_replaced_no_match(load_db, caplog):
    london = et.XML('<replace code="Y">'
                    '<name old="Yorkshire">Greater Yorkshire</name>'
                    '</replace>')

    with database_session():
        _replace_row(models.Region, london)

    log = (LOGGER, logging.WARNING,
           "Region: No rows matching {'code': 'Y'} found.")
    assert log in caplog.record_tuples

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == [("GB", "Great Britain"),
                                                   ("L", "Greater London")]


def test_modify_data(load_db, caplog):
    xml = MODIFY_XML
    modify_data(io.BytesIO(xml))

    log = (LOGGER, logging.INFO, "Rows: 2 created, 1 deleted and 1 replaced.")
    assert log in caplog.record_tuples

    regions = models.Region.query.order_by("code").all()
    assert [(r.code, r.name) for r in regions] == [
        ("L", "London"), ("S", "Scotland"), ("Y", "Yorkshire")
    ]


def test_modify_data_no_model():
    xml = MODIFY_XML.replace(b' model="Region"', b"")
    with pytest.raises(ValueError, match="Every <table> element in"):
        modify_data(io.BytesIO(xml))


def test_modify_data_wrong_model():
    xml = MODIFY_XML.replace(b'model="Region"', b'model="SomeTable"')
    with pytest.raises(ValueError, match="Every <table> element in"):
        modify_data(io.BytesIO(xml))
