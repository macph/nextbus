"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
import collections
import contextlib
import functools
import logging

import click
import dateutil.parser as dp
from flask import current_app
import lxml.etree as et
import sqlalchemy.dialects.postgresql as pg_sql

from nextbus import db


NXB_EXT_URI = r"http://nextbus.org/functions"

logger = logging.getLogger().getChild("populate")
logger.setLevel(logging.INFO)


@contextlib.contextmanager
def database_session():
    """ Commits changes to database within context, or rollback changes and
        raise exception if it runs into one, before closing the session.
    """
    try:
        yield
        db.session.commit()
    except:
        db.session.rollback()
        raise
    finally:
        db.session.remove()


def xml_as_dict(element):
    """ Helper function to create a dictionary from a XML element.

        :param element: XML Element object
        :returns: A dictionary with keys matching subelement tags in the
        element.
    """
    return {i.tag: i.text for i in element}


def ext_function_text(function):
    """ Converts XPath query result to a string by taking the text content from
        the only element in list before passing it to the extension function.
        If the XPath query returned nothing, the wrapped function will return
        None.
    """
    @functools.wraps(function)
    def _function_with_text(instance, context, result, *args, **kwargs):
        if len(result) == 1:
            try:
                text = result[0].text
            except AttributeError:
                text = str(result[0])
            return function(instance, context, text, *args, **kwargs)
        elif len(result) > 1:
            raise ValueError("XPath query returned multiple elements.")
        else:
            return None

    return _function_with_text


class XSLTExtFunctions(object):
    """ Extension for modifying data in NaPTAN/NPTG data. """

    @ext_function_text
    def replace(self, _, result, original, substitute):
        """ Replace substrings within content. """
        return result.replace(original, substitute)

    @ext_function_text
    def upper(self, _, result):
        """ Convert all letters in content to uppercase. """
        return result.upper()

    @ext_function_text
    def lower(self, _, result):
        """ Convert all letters in content to lowercase. """
        return result.lower()

    @ext_function_text
    def remove_spaces(self, _, result):
        """ Remove all spaces from content. """
        return "".join(result.strip())

    @ext_function_text
    def capitalize(self, _, result):
        """ Capitalises every word in a string, include these enclosed within
            brackets and excluding apostrophes.
        """
        list_words = result.lower().split()
        for _w, word in enumerate(list_words):
            for _c, char in enumerate(word):
                if char.isalpha():
                    list_words[_w] = word[:_c] + char.upper() + word[_c+1:]
                    break
        return " ".join(list_words)


def get_atco_codes():
    """ Helper function to get list of ATCO codes from config. """
    get_atco_codes = current_app.config.get("ATCO_CODES")
    if get_atco_codes == "all":
        codes = None
    elif isinstance(get_atco_codes, list):
        # Add ATCO area code 940 for trams
        try:
            codes = [int(i) for i in get_atco_codes]
        except ValueError as err:
            raise ValueError("All ATCO codes must be integers.") from err
        if 940 not in codes:
            codes.append(940)
    else:
        raise ValueError("ATCO codes must be set to either 'all' or a list of "
                         "codes to filter.")

    return codes


class DBEntries(object):
    """ Collects a list of database entries from XML data and commits them. """
    def __init__(self, xml_data):
        self.data = et.parse(xml_data)
        self.entries = collections.OrderedDict()
        self.conflicts = {}

    def add(self, xpath_query, model, func=None, constraint=None,
            indices=None):
        """ Iterates through a list of elements, creating a list of dicts.

            With a parsing function, each entry can be filtered out or
            modified. Can add constraint or indices to use in PostgreSQL's
            INSERT ON CONFLICT DO UPDATE statements. All existing rows are
            deleted before iterating.

            :param xpath_query: XPath query to retrieve list of elements
            :param model: Database model
            :param label: Label for the progress bar
            :param func: Function to evaluate each new object, with two
            arguments - list of existing objects and the current object being
            evaluated. Not expected to return anything
            :param constraint: Name of constraint to evaluate in case of a
            ON CONFLICT DO UPDATE statement
            :param indices: Sequence of string or Column objects to assess
            in a ON CONFLICT DO UPDATE statement
        """
        # Find all elements matching query
        list_elements = self.data.xpath(xpath_query)
        # Assuming keys in every entry are equal
        columns = xml_as_dict(list_elements[0]).keys()

        if constraint is not None and indices is not None:
            raise TypeError("The 'constraint' and 'indices' arguments are "
                            "mutually exclusive.")
        elif constraint is not None:
            self.conflicts[model] = {"constraint": constraint,
                                     "columns": columns}
        elif indices is not None:
            self.conflicts[model] = {"indices": indices, "columns":columns}

        # Create list for model and iterate over all elements
        new_entries = self.entries.setdefault(model, [])
        logger.info("Parsing %d %s elements" %
                    (len(list_elements), model.__name__))
        for element in list_elements:
            data = xml_as_dict(element)
            if data.get("modified") is not None:
                data["modified"] = dp.parse(data["modified"])
            if not func:
                new_entries.append(data)
                continue
            try:
                func(new_entries, data)
            except TypeError as err:
                if "positional argument" in str(err):
                    raise TypeError(
                        "Filter function must receive two arguments: list "
                        "of existing objects and the current object."
                    ) from err
                else:
                    raise

    def _create_insert_statement(self, model):
        """ Creates an insert statement, depending on whether constraints or
            indices were added.

            :param model: Database model
            :returns: Insert statement to be used by the session.execute()
            function. Values are not included as the execute
            function will add them
        """
        table = model.__table__
        if self.conflicts.get(model):
            # Constraint or indices have been specified; make a INSERT ON
            # CONFLICT DO UPDATE statement
            insert = pg_sql.insert(table)
            # Create arguments, add index elements or constraints
            # 'excluded' is a specific property used in ON CONFLICT statements
            # referring to the inserted row conflicting with an existing row
            args = {
                "set_": {c: getattr(insert.excluded, c) for c in
                         self.conflicts[model]["columns"]},
                "where": table.c.modified < insert.excluded.modified
            }
            if "constraint" in self.conflicts[model]:
                args["constraint"] = self.conflicts[model]["constraint"]
            else:
                args["index_elements"] = self.conflicts[model]["indices"]
            statement = insert.on_conflict_do_update(**args)
        else:
            # Else, a simple INSERT statement
            statement = table.insert()

        return statement

    def commit(self):
        """ Commits all entries to database. """
        if not self.entries:
            raise ValueError("No data have been added yet.")
        with database_session():
            for model, data in self.entries.items():
                # Delete existing rows
                db.session.execute(model.__table__.delete())
                # Add new rows
                logger.info(
                    "Deleting old objects and inserting %d %s object%s into "
                    "database" % (len(data), model.__name__,
                                  "" if len(data) == 1 else "s")
                )
                db.session.execute(self._create_insert_statement(model), data)
