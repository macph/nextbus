"""
Utilities for the populate subpackage.
"""
import collections
import contextlib
import functools
import itertools
import logging

from flask import current_app
import lxml.etree as et
import sqlalchemy.dialects.postgresql as pg_sql

from nextbus import db, logger


NXB_EXT_URI = r"http://nextbus.org/functions"
ROW_LIMIT = 10000

logger = logger.app_logger.getChild("populate")
logger.setLevel(logging.INFO)


@contextlib.contextmanager
def database_session():
    """ Commits changes to database within context, or rollback changes and
        raise exception if it runs into one, before closing the session.

        With SQLAlchemy's autocommit config set to True, the begin() method is
        unnecessary.
    """
    try:
        yield
        db.session.commit()
    except:
        db.session.rollback()
        logger.error("An error occured during the transcation", exc_info=1)
        raise
    finally:
        db.session.remove()


def batch_insert(statement, list_rows, limit=None):
    """ Executes multi-valued inserts in batches.

        :param statement: Statement to be executed.
        :param list_rows: Iterable of dictionaries to be added.
        :param limit: Limit on rows in each batch - if None ROW_LIMIT is used.
    """
    _limit = ROW_LIMIT if limit is None else limit
    iter_rows = iter(list_rows)
    while True:
        chunk = list(itertools.islice(iter_rows, _limit))
        if not chunk:
            break
        db.session.execute(statement.values(chunk))


def xml_as_dict(element):
    """ Helper function to create a dictionary from a XML element.

        :param element: XML Element object
        :returns: A dictionary with keys matching subelement tags in the
        element.
    """
    return {i.tag: i.text for i in element}


def ext_function_text(func):
    """ Converts XPath query result to a string by taking the text content from
        the only element in list before passing it to the extension function.
        If the XPath query returned nothing, the wrapped function will return
        None.
    """
    @functools.wraps(func)
    def ext_function_with_text(context, result, *args, **kwargs):
        if len(result) == 1:
            try:
                text = result[0].text
            except AttributeError:
                text = str(result[0])
            return func(context, text, *args, **kwargs)
        elif len(result) > 1:
            raise ValueError("XPath query returned multiple elements.")
        else:
            return None

    return ext_function_with_text


xslt_func = et.FunctionNamespace(NXB_EXT_URI)


@xslt_func
@ext_function_text
def replace(_, result, original, substitute):
    """ Replace substrings within content. """
    return result.replace(original, substitute)


@xslt_func
@ext_function_text
def upper(_, result):
    """ Convert all letters in content to uppercase. """
    return result.upper()


@xslt_func
@ext_function_text
def lower(_, result):
    """ Convert all letters in content to lowercase. """
    return result.lower()


@xslt_func
@ext_function_text
def remove_spaces(_, result):
    """ Remove all spaces from content. """
    return "".join(result.strip())


@xslt_func
@ext_function_text
def capitalize(_, result):
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
    atco_codes = current_app.config.get("ATCO_CODES")
    if atco_codes is None:
        codes = atco_codes
    elif isinstance(atco_codes, list):
        # Add ATCO area code 940 for trams
        try:
            codes = [int(i) for i in atco_codes]
        except ValueError as err:
            raise ValueError("All ATCO codes must be integers.") from err
        if 940 not in codes:
            codes.append(940)
    else:
        raise ValueError("ATCO codes must be set to either None or a list of "
                         "codes to filter.")

    return codes


class DBEntries(object):
    """ Collects a list of database entries from XML data and commits them. """
    def __init__(self, xml_data=None):
        self.data = None
        if xml_data is not None:
            self.set_data(xml_data)
        self.entries = collections.OrderedDict()
        self.conflicts = {}

    def set_data(self, xml_data):
        """ Sets the source XML data to a new ElementTree object. """
        try:
            self.data = et.parse(xml_data)
        except TypeError:
            self.data = xml_data

    def add(self, xpath_query, model, func=None, indices=None):
        """ Iterates through a list of elements, creating a list of dicts.

            With a parsing function, each entry can be filtered out or
            modified. Can add constraint or indices to use in PostgreSQL's
            INSERT ON CONFLICT DO UPDATE statements. All existing rows are
            deleted before iterating.

            :param xpath_query: XPath query to retrieve list of elements
            :param model: Database model
            :param func: Function to evaluate each new object, with the current
            object being evaluated as the only argument.
            :param indices: Sequence of string or Column objects, which should
            be unique, to assess in a ON CONFLICT DO UPDATE statement
        """
        if self.data is None:
            raise ValueError("No source XML data has been set.")
        # Find all elements matching query
        list_elements = self.data.xpath(xpath_query)

        # Check indices and add them for INSERT ON CONFLICT statements
        if indices is not None:
            self.conflicts[model] = indices

        if self.entries.get(model) is None:
            self.entries[model] = []
        new_entries = self.entries[model]

        if not list_elements:
            return

        logger.info("Parsing %d %s elements" %
                    (len(list_elements), model.__name__))
        # Create list for model and iterate over all elements
        for element in list_elements:
            data = xml_as_dict(element)
            if func is not None:
                try:
                    new_data = func(data)
                    if new_data is None:
                        continue
                    else:
                        data = new_data
                except TypeError as err:
                    if "positional argument" in str(err):
                        raise TypeError(
                            "Filter function must receive the current object "
                            "as the only argument."
                        ) from err
                    else:
                        raise

            new_entries.append(data)

    def _check_duplicates(self):
        """ Does a Python-side check of duplicates before executing INSERT
            statements.

            INSERT ON CONFLICT DO UPDATE statements work better with single
            tuples of values, but we are using multi-valued inserts here.
        """
        for model in self.conflicts:
            removed = 0
            indices = self.conflicts[model]
            found = {}
            for entry in self.entries[model]:
                try:
                    i = tuple(entry[i] for i in indices)
                except KeyError as err:
                    raise KeyError("Field names %r does not exist for model %s"
                                   % (indices, model.__name__)) from err
                if i not in found or entry["modified"] > found[i]["modified"]:
                    found[i] = entry
                else:
                    removed += 1
            if removed > 0:
                logger.info("%d duplicate %s objects removed" %
                            (removed, model.__name__))
            self.entries[model] = list(found.values())

    def commit(self):
        """ Commits all entries to database. """
        if not self.entries:
            raise ValueError("No data have been added yet.")
        self._check_duplicates()
        with database_session():
            for model, data in self.entries.items():
                # Delete existing rows
                logger.info("Deleting old %s objects" % model.__name__)
                db.session.execute(model.__table__.delete())
                # Add new rows
                logger.info("Inserting %d %s objects into database" %
                            (len(data), model.__name__))
                batch_insert(model.__table__.insert(), data)
