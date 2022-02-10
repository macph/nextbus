"""
Modify populated data with list of modify and delete entries, for example to
handle errata in stop point names.
"""
from importlib.resources import open_binary

import dateutil.parser as dp
import lxml.etree as et

from nextbus import db, models
from nextbus.populate import utils


logger = utils.logger.getChild("modify")


def _match_attr(model, attr):
    match_attr = (getattr(model, k) == v for k, v in attr.items())
    return db.and_(*match_attr)


def _create_row(connection, model, element):
    """ Adds new row to table with data from this element whose subelements
        have the same tags as table columns.

        Data whose columns match DateTime columns will be converted to DateTime
        objects.

        :param connection: Connection for population.
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

    connection.execute(db.insert(model).values(data))

    return 1


def _delete_row(connection, model, element):
    """ Deletes rows from table matching attributes from this element.

        :param connection: Connection for population.
        :param model: The database model class.
        :param element: A ``delete`` XML element.
        :returns: Number of rows deleted.
    """
    name = model.__name__
    if not element.keys():
        raise ValueError("Each <delete> element requires at least one XML "
                         "attribute to filter rows.")

    delete_row = connection.execute(
        db.delete(model).where(_match_attr(model, element.attrib))
    )
    count = delete_row.rowcount
    if count == 0:
        logger.warning(f"{name}: No rows matching {element.attrib} found.")

    return count


def _replace_row(connection, model, element):
    """ Replaces values for rows in tables matching attributes from this
        element.

        :param connection: Connection for population.
        :param model: The database model class.
        :param element: A ``replace`` XML element.
        :returns: Number of rows replaced.
    """
    name = model.__name__
    if not element.keys():
        raise ValueError("Each <replace> element requires at least one XML "
                         "attribute to filter rows.")

    matching = connection.execute(
        db.select([model.__table__]).where(_match_attr(model, element.attrib))
    )
    matching_entries = matching.fetchall()
    if not matching_entries:
        logger.warning(f"{name}: No rows matching {element.attrib} found.")
        return 0

    updated_values = {}
    for value in element:
        column = value.tag
        old_value = value.get("old")
        new_value = value.text
        existing = set(getattr(r, column) for r in matching_entries)
        # Checks if new values already exist
        if existing == {new_value}:
            logger.warning(f"{name}: {column} {new_value!r} for "
                           f"{element.attrib} already matches.")
            continue
        # Gives a warning if set value does not match the existing
        # value, suggesting it may have been changed in the dataset
        if old_value and not all(e == old_value for e in existing):
            if len(existing) > 1:
                values = f"values {sorted(existing)}"
            else:
                values = f"value {next(iter(existing))!r}"
            logger.warning(f"{name}: {column} {old_value!r} for "
                           f"{element.attrib} does not match existing "
                           f"{values}.")
        updated_values[column] = new_value

    if updated_values:
        # Update matched entries
        update_matching = connection.execute(
            db.update(model)
            .values(updated_values)
            .where(_match_attr(model, element.attrib))
        )
        return update_matching.rowcount
    else:
        return 0


def modify_data(connection, xml_file=None):
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
    if xml_file is None:
        with open_binary("nextbus.populate", "modify.xml") as file_:
            data = et.parse(file_)
    else:
        data = et.parse(xml_file)

    list_tables = data.xpath("table")
    if not all(hasattr(models, t.get("model", "")) for t in list_tables):
        raise ValueError("Every <table> element in the data must have a "
                         "'model' attribute matching an existing table.")

    logger.info("Processing populated data")
    c, d, r = 0, 0, 0
    with connection.begin():
        for table in list_tables:
            model = getattr(models, table.get("model"))
            for element in table.xpath("create"):
                c += _create_row(connection, model, element)
            for element in table.xpath("delete"):
                d += _delete_row(connection, model, element)
            for element in table.xpath("replace"):
                r += _replace_row(connection, model, element)

    logger.info(f"Rows: {c} created, {d} deleted and {r} replaced.")
