"""
Utilities for the populate subpackage.
"""
import collections
import contextlib
import datetime
import functools
import itertools
import logging
import os
import re
import shutil
import tempfile
import types

import dateutil.parser as dp
from flask import current_app
import lxml.etree as et
import psycopg2.sql
from sqlalchemy.dialects import postgresql

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
        logger.error("An error occurred during the transaction", exc_info=1)
        raise
    finally:
        db.session.remove()


@contextlib.contextmanager
def database_connection():
    """ Opens a connection to database and commits changes within context.
        Changes are rolled back and exceptions raised if any errors are
        encountered.
    """
    try:
        with db.engine.begin() as connection:
            yield connection
    except:
        logger.error("An error occurred during the transaction", exc_info=1)
        raise


def reflect_metadata():
    """ Retrieves metadata from the DB. """
    metadata = db.MetaData()
    metadata.reflect(db.engine)

    return metadata


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


xslt_func = et.FunctionNamespace(NXB_EXT_URI)


def xslt_text_func(func, _name=None):
    """ Registers a XSLT function with all arguments converted into text from
        single elements.

        If multiple elements are returned in an argument, ValueError is raised.

        :param func: Function to be registered or name of registered function
        :param _name: Internal parameter for registering function name
    """
    if not callable(func):
        return lambda f: xslt_text_func(f, _name=func)

    @functools.wraps(func)
    def func_with_text(*args):
        list_ = list(args)
        is_method = isinstance(func, types.MethodType)
        # If a method, pass through both self/cls and XSLT context
        context = list_[:2] if is_method else list_[:1]
        user_args = list_[2:] if is_method else list_[1:]

        new = []
        for result in user_args:
            # Get single element from result list
            try:
                if isinstance(result, str) or result is None:
                    element = result
                elif len(result) == 0:
                    element = None
                elif len(result) == 1:
                    element = result[0]
                else:
                    raise ValueError("XPath query returned multiple elements.")
            except TypeError:
                element = result

            try:
                text = element.text
            except AttributeError:
                text = str(element) if element is not None else None

            new.append(text)

        return func(*tuple(context), *tuple(new))

    if _name is not None:
        func_with_text.__name__ = _name

    return xslt_func(func_with_text)


@xslt_text_func
def replace(_, result, original, substitute):
    """ Replace substrings within content. """
    return result.replace(original, substitute)


@xslt_text_func
def upper(_, text):
    """ Convert all letters in content to uppercase. """
    return text.upper()


@xslt_text_func
def lower(_, text):
    """ Convert all letters in content to lowercase. """
    return text.lower()


@xslt_text_func
def capitalize(_, text):
    """ Capitalises every word in a string, include these enclosed within
        brackets and excluding apostrophes.
    """
    list_words = text.lower().split()
    for _w, word in enumerate(list_words):
        for _c, char in enumerate(word):
            if char.isalpha():
                list_words[_w] = word[:_c] + char.upper() + word[_c+1:]
                break

    return " ".join(list_words)


@xslt_text_func
def l_split(_, text, char):
    """ Strips string to left of and including specified characters."""
    return text.split(char)[0]


@xslt_text_func
def r_split(_, text, char):
    """ Strips string to left of and including specified characters."""
    return text.split(char)[-1]


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


class PopulateData:
    def __init__(self):
        self.input = None
        self.entries = collections.OrderedDict()

        self.metadata = reflect_metadata()
        self.dc = DataCopy(self.metadata)

    def total(self):
        return sum(len(e) for e in self.entries.values())

    def set_input(self, xml_data):
        """ Sets source data to a XML file or ElementTree object.

            :param xml_data: `ElementTree` object, a file-like object or a path
            pointing to a XML file.
        """
        try:
            self.input = et.parse(xml_data)
        except TypeError:
            self.input = xml_data

    def add(self, xpath_query, model):
        """ Iterates through a list of elements, creating a list of dicts.

            :param xpath_query: XPath query to retrieve list of elements.
            :param model: Database model.
        """
        if self.input is None:
            raise ValueError("No source XML data has been set yet.")

        # Find all elements matching query
        list_elements = self.input.xpath(xpath_query)
        if not list_elements:
            return

        new_entries = self.entries.setdefault(model, list())
        new_entries.extend(xml_as_dict(e, False) for e in list_elements)

    def _new_temp_table(self, table):
        """ Creates a temporary table based on an existing table, excluding any
            columns with autoincrement, and set it to drop on commit.
        """
        # Find a suitable temporary table name
        num = 0
        temp_name = "%s_%d" % (table.name, num)
        while temp_name in self.metadata.tables:
            num += 1
            temp_name = "%s_%d" % (table.name, num)

        new_columns = [db.Column(c.name, c.type, autoincrement=False)
                       for c in table.columns if not c.autoincrement]

        return db.Table(
            temp_name,
            self.metadata,
            *new_columns,
            prefixes=["TEMPORARY"],
            postgresql_on_commit="DROP"
        )

    def _commit(self, connection, model, delete=False):
        """ Copies from entries for a model using a temporary table. """
        if not self.entries[model]:
            return

        table = self.metadata.tables[model.__tablename__]
        temp_table = self._new_temp_table(table)
        temp_table.create(connection)

        # Add entries to temporary table using COPY
        self.dc.copy(connection, temp_table, self.entries[model])

        if delete:
            truncate(connection, table)

        insert_main = (
            postgresql.insert(table)
            .from_select([c.name for c in temp_table.columns],
                         db.select([temp_table]))
            .on_conflict_do_nothing()
        )

        logger.info("Inserting all data from temporary table %r for model %s" %
                    (temp_table.name, model.__name__))
        connection.execute(insert_main)

        self.metadata.remove(temp_table)

    def commit(self, delete=False, exclude=None, clear=False):
        """ Copies data from XML data which has been added.
            :param delete: Delete old data from models before copying.
            :param exclude: Iterable of models that shouldn't be deleted
            :param clear: Delete all entries after committing.
        """
        with database_connection() as conn:
            for m in self.entries:
                delete_model = delete and (exclude is None or m not in exclude)
                self._commit(conn, m, delete_model)
        if clear:
            self.entries.clear()


def truncate(connection, table, cascade=True):
    """ Deletes data from a table using `TRUNCATE`.

        :param connection: SQLAlchemy engine connection.
        :param table: SQLAlchemy `Table` object.
        :param cascade: Truncate other tables with foreign keys to this table.
    """
    str_truncate = "TRUNCATE {} CASCADE;" if cascade else "TRUNCATE {};"
    table_name = psycopg2.sql.Identifier(table.name)
    statement = psycopg2.sql.SQL(str_truncate).format(table_name)

    with connection.connection.cursor() as cursor:
        logger.info("Deleting all rows from %r" % table.name)
        cursor.execute(statement)


class DataCopy(object):
    """ Sets up an interface for copying data to PostgreSQL DB. """
    SEP = "\t"
    NULL = r"\N"
    LIMIT = 500000

    def __init__(self, metadata=None):
        # Get metadata from existing database for server defaults
        if metadata is not None:
            self.metadata = metadata
        else:
            self.metadata = reflect_metadata()

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
                    # Remove trailing/leading spaces and escape backslash
                    # characters and delimiters within values
                    value = (
                        value.strip()
                        .replace("\\", "\\\\")
                        .replace("\n", "\\" + "\n")
                        .replace(self.SEP, "\\" + self.SEP)
                    )
                else:
                    value = self.NULL
                row.append(value)
                columns.append(col.name)
            elif not col.nullable and col.server_default is None:
                raise ValueError(
                    "Non-nullable column %r for table %r does not have a "
                    "default value; can't use row %r without this column." %
                    (table.name, col.name, obj)
                )

        return row, columns

    def _write_copy_file(self, file_, table_name, data):
        """ Writes data from list of dicts to a file for import. """
        table = self.metadata.tables[table_name]
        columns = None
        for obj in data:
            row, cols = self._parse_row(table, obj)
            # Compare columns to ensure they are all the same
            if columns is None:
                columns = cols
            elif cols != columns:
                raise ValueError(
                    "Columns %r for this row in table %r differ from columns "
                    "%r for other rows." % (cols, table_name, columns)
                )

            file_.write(self.SEP.join(row) + "\n")

        return columns

    def _create_copy_files(self, table_name, data):
        """ Splits data into chunks with `LIMIT` and saves them to files. """
        iter_rows = iter(data)
        temp_files = []
        columns = None

        try:
            while True:
                chunk = list(itertools.islice(iter_rows, self.LIMIT))
                if not chunk:
                    break
                # Create a temporary file to store copy data
                fd, path = tempfile.mkstemp()
                with open(fd, "w") as file_:
                    columns = self._write_copy_file(file_, table_name, chunk)
                temp_files.append(path)
        except:
            for path in temp_files:
                os.remove(path)
            raise

        return columns, temp_files

    def _copy_from_file(self, cursor, table_name, columns, path):
        """ Opens file and copies it to the DB using `COPY FROM`. If any errors
            occur the offending file is saved to `temp/error_data`.
        """
        with open(path) as file_:
            try:
                cursor.copy_from(file_, table_name, sep=self.SEP,
                                 null=self.NULL, columns=columns)
            except:
                # Save copy file for debugging and raise again
                error_file = "temp/error_data"
                logger.error("Error occurred with COPY; saving file to "
                             "%r" % error_file)
                logger.debug("Columns: %r" % columns)
                with open(error_file, "w") as f:
                    file_.seek(0)
                    shutil.copyfileobj(file_, f)
                raise

    def copy(self, connection, table, data):
        """ Copies all data to the database, deleting data afterwards

            :param table: SQLAlchemy `Table` object.
            :param data: List of dictionaries with table columns as keys. All
            dictionaries must have the same keys.
            :param connection: SQLAlchemy engine connection.
        """
        logger.info("Copying %d row%s to %r" %
                    (len(data), "" if len(data) == 1 else "s", table.name))
        columns, temp_files = self._create_copy_files(table.name, data)

        try:
            with connection.connection.cursor() as cursor:
                for path in temp_files:
                    self._copy_from_file(cursor, table.name, columns, path)
        finally:
            for path in temp_files:
                os.remove(path)
