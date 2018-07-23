"""
Utilities for the populate subpackage.
"""
import collections
import contextlib
import datetime
import functools
import itertools
import logging
import re

import dateutil.parser as dp
from flask import current_app
import lxml.etree as et

from nextbus import db, logger


NXB_EXT_URI = r"http://nextbus.org/functions"
ROW_LIMIT = 10000
# Parses an ISO8601 duration string, eg 'P1Y2M3DT4H5M6.7S'
PARSE_DURATION = re.compile(
    r"^(|[-+])P(?=.+)(?:(?:)|(\d+)Y)(?:(?:)|(\d+)M)(?:(?:)|(\d+)D)"
    r"(?:T?(?:)(?:)(?:)|T(?:(?:)|(\d+)H)(?:(?:)|(\d+)M)"
    r"(?:(?:)|(\d*\.?\d+|\d+\.?\d*)S))$"
)

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


def duration_delta(duration, ignore=False):
    """ Converts a time duration from XML data to a timedelta object.

        If the 'ignore' parameter is set to False, specifying a year or month
        value other than zero will raise an exception as they cannot be used
        without context.

        :param duration: Duration value obtained from XML element
        :param ignore: If True, will ignore non zero year or month values
        instead of raising exception
        :returns: timedelta object
    """
    match = PARSE_DURATION.match(duration)
    if not match:
        raise ValueError("Parsing %r failed - not a valid XML duration value."
                         % duration)

    if not ignore and any(i is not None and int(i) != 0 for i in
                          [match.group(2), match.group(3)]):
        raise ValueError("Year and month values cannot be used in timedelta "
                         "objects - they need context.")

    def convert(group, func):
        return func(group) if group is not None else 0

    delta = datetime.timedelta(
        days=convert(match.group(4), int),
        hours=convert(match.group(5), int),
        minutes=convert(match.group(6), int),
        seconds=convert(match.group(7), float)
    )

    if match.group(1) == '-':
        delta *= -1

    return delta


def xml_as_dict(element, convert=True):
    """ Creates a dictionary from a flat XML element. If convert is True,
        ``py_type`` attributes are used to coerce values.

        If another attribute ``py_null`` is truthy or omitted, the value None
        can be returned for an empty element otherwise the default conversion
        value (eg ``str()``) is used.

        Types:
        - ``bool``: Converts boolean strings such as 0 or true.
        - ``int``: integers
        - ``float``: floating point numbers
        - ``datetime``: Parsed as datetime objects

        :param element: XML Element object
        :param convert: If True, use attributes to convert values. The
        :returns: A dictionary with keys matching subelement tags in the
        element.
    """
    def _bool(value="0"):
        if value in {"1", "true"}:
            return True
        elif value in {"0", "false"}:
            return False
        else:
            raise ValueError("%r does not represent a boolean value." % value)

    convs = {
        "bool": _bool,
        "str": str,
        "int": int,
        "float": float,
        "datetime": dp.parse,
        "duration": duration_delta
    }

    data = {}
    for i in element:
        if i.tag in data:
            raise ValueError("Multiple elements have the same tag %r." % i.tag)

        nullable = "py_null" not in i.keys() or _bool(i.get("py_null"))
        type_ = i.get("py_type")
        if convert and type_ is not None:
            conv = convs.get(type_)
            if conv is None:
                raise ValueError("Invalid py_type attribute: %r" % type_)
        else:
            conv = str

        try:
            if i.text is not None:
                data[i.tag] = conv(i.text)
            elif not nullable:
                data[i.tag] = conv()
            else:
                data[i.tag] = None
        except (TypeError, ValueError) as err:
            raise ValueError("Text %r cannot be converted with type %r." %
                             (i.text, type_)) from err

    return data


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
    def __init__(self, xml_data=None, log_each=True):
        self.data = None
        if xml_data is not None:
            self.set_data(xml_data)
        self.entries = collections.OrderedDict()
        self.conflicts = {}
        self.log_each = log_each

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

        if self.log_each:
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

    def _check_duplicates(self, warn=False):
        """ Does a Python-side check of duplicates before executing INSERT
            statements.

            If a 'modified' column exists, it is used to find the most recent
            version, otherwise duplicates are checked on their contents and
            raising a ValueError if they differ.

            INSERT ON CONFLICT DO UPDATE statements work better with single
            tuples of values, but we are using multi-valued inserts here.

            :param warn: Logs a warning for conflicting entries that are not
            equal, with extra entries discarded. If False, an error is raised.
        """
        for model in self.conflicts:
            removed = 0
            indices = self.conflicts[model]
            found = {}
            for entry in self.entries[model]:
                try:
                    i = tuple(entry[j] for j in indices)
                except KeyError as err:
                    raise KeyError("Field names %r does not exist for model %s"
                                   % (indices, model.__name__)) from err
                current = entry.get("modified")
                if i not in found:
                    found[i] = entry
                elif current is not None and current > found[i]["modified"]:
                    found[i] = entry
                elif current is None and entry != found[i]:
                    if warn:
                        logger.warn(
                            "Entries %r and %r for model %s do not match" %
                            (entry, found[i], model.__name__)
                        )
                    else:
                        # Not comparing on last modified dates but values do
                        # not match - no way to tell which to pick. Raise error
                        raise ValueError(
                            "Entries %r and %r do not match. Without last "
                            "modified dates they cannot be picked." %
                            (entry, found[i])
                        )
                else:
                    removed += 1
            if removed > 0:
                logger.info("%d duplicate %s objects removed" %
                            (removed, model.__name__))
            self.entries[model] = list(found.values())

    def commit(self, delete=False):
        """ Commits all entries to database. """
        if not self.entries:
            raise ValueError("No data have been added yet.")
        self._check_duplicates(warn=True)
        with database_session():
            for model, data in self.entries.items():
                if delete:
                    # Delete existing rows
                    logger.info("Deleting old %s objects" % model.__name__)
                    db.session.execute(model.__table__.delete())
                # Add new rows
                logger.info("Inserting %d %s objects into database" %
                            (len(data), model.__name__))
                batch_insert(model.__table__.insert(), data)
