"""
Modify populated data with list of modify and delete entries, for example to
handle errata in stop point names.
"""
import os

import dateutil.parser as dp
import lxml.etree as et

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import utils


logger = utils.logger.getChild("modify")
POST_XML_PATH = os.path.join(ROOT_DIR, "nextbus/populate/modify.xml")


def _create_row(model, element):
    """ Adds new row to table with data from this element whose subelements
        have the same tags as table columns.

        Data whose columns match DateTime columns will be converted to DateTime
        objects.

        :param model: The database model class.
        :param element: A ``create`` XML element.
        :returns: Number of rows created.
    """
    data = utils.xml_as_dict(element)

    if not data:
        raise ValueError("Each <create> element requires at least one sub "
                         "element with field entries.")

    for key in data:
        column = model.__table__.columns.get(key)
        # Check if types match DateTime and use datetime parser
        if isinstance(column.type, db.DateTime) and data.get(key) is not None:
            data[key] = dp.parse(data[key])

    db.session.add(model(**data))

    return 1


def _delete_row(model, element):
    """ Deletes rows from table matching attributes from this element.

        :param model: The database model class.
        :param element: A ``delete`` XML element.
        :returns: Number of rows deleted.
    """
    if not element.keys():
        raise ValueError("Each <delete> element requires at least one XML "
                         "attribute to filter rows.")

    count = model.query.filter_by(**element.attrib).delete()
    if count == 0:
        logger.warning("%s: No rows matching %r found." %
                       (model.__name__, element.attrib))

    return count


def _replace_row(model, element):
    """ Replaces values for rows in tables matching attributes from this
        element.

        :param model: The database model class.
        :param element: A ``replace`` XML element.
        :returns: Number of rows replaced.
    """
    name = model.__name__
    if not element.keys():
        raise ValueError("Each <replace> element requires at least one XML "
                         "attribute to filter rows.")

    matching = model.query.filter_by(**element.attrib)
    matching_entries = matching.all()
    if not matching_entries:
        logger.warning("%s: No rows matching %r found." %
                       (name, element.attrib))
        return 0

    updated_values = {}
    for value in element:
        column = value.tag
        old_value = value.get("old")
        new_value = value.text
        existing = set(getattr(r, column) for r in matching_entries)
        # Checks if new values already exist
        if existing == {new_value}:
            logger.warning(
                "%s: %s %r for %r already matches." %
                (name, column, new_value, element.attrib)
            )
            continue
        # Gives a warning if set value does not match the existing
        # value, suggesting it may have been changed in the dataset
        if old_value and not all(e == old_value for e in existing):
            if len(existing) > 1:
                values = "values %r" % sorted(existing)
            else:
                values = "value %r" % next(iter(existing))
            logger.warning(
                "%s: %s %r for %r does not match existing %s." %
                (name, column, old_value, element.attrib, values)
            )
        updated_values[column] = new_value

    if updated_values:
        # Update matched entries
        return matching.update(updated_values)
    else:
        return 0


def _load_xml_file(xml_file):
    """ Finds path for XML file used to modify data and opens it; it can be
        relative to ROOT_PATH, an absolute path or a file-like object.

        :param xml_file: Path to the XML file or a file-like object.
        :returns: lxml.etree.ElementTree object.
    """
    try:
        if xml_file is not None and os.path.isabs(xml_file):
            xml_path = xml_file
        elif xml_file is not None:
            xml_path = os.path.join(ROOT_DIR, xml_file)
        else:
            xml_path = POST_XML_PATH
    except TypeError as err:
        if "expected str, bytes or os.PathLike object" in str(err):
            # Assume to be a file-like object, for example an opened file
            xml_path = xml_file
        else:
            raise

    return et.parse(xml_path)


def modify_data(xml_file=None):
    """ Function to modify data after population from creating, deleting and
        replacing rows with a XML file.

        Each subelement must have a model name corresponding to an existing
        table. Each table has a number of ``create``, ``delete`` and
        ``replace`` elements.

        - ``create``: Elements with same names as columns.
        - ``delete``: Attributes used to identify rows to delete.
        - ``replace``: Attributes used to identify rows to modify, with
        elements with same names as columns and optional ``old`` attribute. If
        the old value does not match existing values, a warning is issued.
    """
    data = _load_xml_file(xml_file)
    list_tables = data.xpath("table")
    if not all(hasattr(models, t.get("model", "")) for t in list_tables):
        raise ValueError("Every <table> element in the data must have a "
                         "'model' attribute matching an existing table.")

    logger.info("Processing populated data")
    create, delete, replace = 0, 0, 0
    for table in list_tables:
        model = getattr(models, table.get("model"))
        with utils.database_session():
            for element in table.xpath("create"):
                create += _create_row(model, element)
            for element in table.xpath("delete"):
                delete += _delete_row(model, element)
            for element in table.xpath("replace"):
                replace += _replace_row(model, element)

    logger.info("Rows: %d created, %d deleted and %d replaced." %
                (create, delete, replace))
