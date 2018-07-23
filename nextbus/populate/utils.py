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
import shutil
import tempfile

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


class PopulateData(object):
    """ Collects a list of database entries from XML data and populate database.
    """
    def __init__(self, xml_data=None):
        self.data = None
        if xml_data is not None:
            self.set_data(xml_data)
        self.entries = collections.OrderedDict()
        self.conflicts = {}
        self.cd = DataCopy()

    def set_data(self, xml_data):
        """ Sets the source XML data to a new ElementTree object. """
        try:
            self.data = et.parse(xml_data)
        except TypeError:
            self.data = xml_data

    def add(self, xpath_query, model, indices=None):
        """ Iterates through a list of elements, creating a list of dicts.

            :param xpath_query: XPath query to retrieve list of elements
            :param model: Database model
            :param indices: Sequence of string or Column objects, which should
            be unique, for checking duplicates
        """
        if self.data is None:
            raise ValueError("No source XML data has been set.")
        # Find all elements matching query
        list_elements = self.data.xpath(xpath_query)

        if indices is not None:
            self.conflicts[model] = indices

        if self.entries.get(model) is None:
            self.entries[model] = []
        new_entries = self.entries[model]

        if not list_elements:
            return
        # Create list for model and iterate over all elements
        for element in list_elements:
            new_entries.append(xml_as_dict(element, convert=False))

    def _process_duplicates(self, model, warn):
        """ Iterates through all entries for a model, removing duplicates.

            If a 'modified' column exists, it is used to find the most recent
            version, otherwise duplicates are checked on their contents and
            raising a ValueError if they differ.

            :param warn: Logs a warning for conflicting entries that are not
            equal, with extra entries discarded. If False, an error is raised.
        """
        indices = self.conflicts[model]
        removed = 0
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
            elif current is not None:
                if dp.parse(current) > dp.parse(found[i]["modified"]):
                    found[i] = entry
                else:
                    removed += 1
            elif entry != found[i]:
                if warn:
                    logger.warn(
                        "Entries %r and %r for model %s do not match" %
                        (entry, found[i], model.__name__)
                    )
                else:
                    # Not comparing on last modified dates but values do
                    # not match - no way to tell which to pick. Raise error
                    raise ValueError(
                        "Entries %r and %r do not match. Without last modified "
                        "dates they cannot be picked." % (entry, found[i])
                    )
            else:
                removed += 1

        if removed > 0:
            logger.info("%d duplicate %s objects removed" %
                        (removed, model.__name__))

        return list(found.values())

    def _check_duplicates(self, warn=False):
        """ Does a Python-side check of duplicates before executing INSERT
            statements.

            INSERT ON CONFLICT DO UPDATE statements work better with single
            tuples of values, but we are using multi-valued inserts here.

            :param warn: Logs a warning for conflicting entries that are not
            equal, with extra entries discarded. If False, an error is raised.
        """
        for model in self.conflicts:
            self.entries[model] = self._process_duplicates(model, warn)

    def commit(self, delete=False):
        """ Commits all entries to database. """
        if not self.entries:
            raise ValueError("No data have been added yet.")
        self._check_duplicates(warn=True)
        self.cd.copy(self.entries, delete=delete)


class DataCopy(object):
    """ Sets up an interface for copying data to DB. """
    SEP = "\t"
    NULL = r"\N"
    LIMIT = 1000000

    def __init__(self):
        # Get metadata from existing database for server defaults
        self.engine = db.session.get_bind()
        self.metadata = db.MetaData()
        self.metadata.reflect(bind=self.engine)

    def _parse_row(self, table, obj):
        """ Parses each object, excluding columns that have server defaults (eg
            sequences).
        """
        row = []
        columns = []
        for col in table.columns:
            if col.name in obj:
                value = obj[col.name]
                if value is not None:
                    # Escape backslash characters and delimiters within values
                    value = value.replace("\\", "\\\\")
                    value = value.replace(self.SEP, "\\" + self.SEP)
                else:
                    value = self.NULL
                row.append(value)
                columns.append(col.name)
            elif not col.nullable and col.server_default is None:
                raise ValueError(
                    "Non-nullable column %r:%r does not have a default value; "
                    "can't use data %r" % (table.name, col.name, obj)
                )

        return row, columns

    def write_copy_file(self, file_, table_name, data):
        """ Writes data from list of dicts to a temporary file for import. """
        table = self.metadata.tables[table_name]
        columns = None
        for obj in data:
            row, cols = self._parse_row(table, obj)
            # Compare columns to ensure they are all the same
            if columns is None:
                columns = cols
            elif cols != columns:
                raise ValueError("Row have different columns %r for "
                                 "table %r." % (cols, table_name))

            file_.write(self.SEP.join(row) + "\n")

        file_.seek(0)  # Rewind file

        return columns

    def _batch_copy(self, cursor, table_name, data):
        """ Iterates over rows in batches. """
        iter_rows = iter(data)
        while True:
            chunk = list(itertools.islice(iter_rows, self.LIMIT))
            if not chunk:
                break

            # Create a temporary file to store copy data
            file_ = tempfile.TemporaryFile(mode="w+")
            columns = self.write_copy_file(file_, table_name, chunk)

            try:
                cursor.copy_from(file_, table_name, sep=self.SEP,
                                 null=self.NULL, columns=columns)
            except:
                # Save copy file for debugging and raise again
                error_file = "temp/error_data"
                logger.error("Error occurred with COPY; saving file to %r" %
                             error_file)
                logger.debug("Columns: %r" % columns)
                with open(error_file, "w") as f:
                    file_.seek(0)
                    shutil.copyfileobj(file_, f)
                raise
            finally:
                file_.close()

    def copy(self, dataset, delete=False):
        """ Copies all data to the database.

            :param dataset: Dict with models as keys and lists of dicts as
            values. All dicts must have the same keys.
            :param delete: Truncates existing data.
        """
        connection = self.engine.raw_connection()
        try:
            with connection.cursor() as cursor:
                for model, data in dataset.items():
                    table_name = model.__tablename__
                    if delete:
                        logger.info("Deleting old %r rows" % table_name)
                        cursor.execute("TRUNCATE %s CASCADE;" % table_name)
                    logger.info("Copying data to %r" % table_name)
                    self._batch_copy(cursor, table_name, data)
            connection.commit()
        except:
            connection.rollback()
            raise
        finally:
            connection.close()
