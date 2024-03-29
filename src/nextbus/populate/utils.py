"""
Utilities for the populate subpackage.
"""
import csv
import functools
import io
import itertools
import logging
import os
import shutil
import tempfile
import types

from flask import current_app
import lxml.etree as et
import psycopg2.sql
from sqlalchemy.dialects import postgresql

from nextbus import db, logger, models


NXB_EXT_URI = r"http://nextbus.org/functions"

ROW_LIMIT = 100000

logger = logger.app_logger.getChild("populate")
logger.setLevel(logging.INFO)


def reflect_metadata(bind):
    """ Retrieves metadata from the DB. """
    metadata = db.MetaData()
    metadata.reflect(bind)

    return metadata


def xml_as_dict(element):
    """ Creates a dictionary from a flat XML element.

        :param element: XML Element object
        :returns: A dictionary with keys matching subelement tags in the
        element.
    """
    data = {}
    for e in element:
        if e.tag in data:
            raise ValueError(f"Multiple elements have the same tag {e.tag!r}.")
        default = e.get("default", None)
        data[e.tag] = default if e.text is None else e.text

    return data


xslt_func = et.FunctionNamespace(NXB_EXT_URI)


def _convert_to_text(result):
    """ Takes first element from list and returns text or None. """
    if isinstance(result, list) and not result:
        node = None
    elif isinstance(result, list) and len(result) == 1:
        node = result[0]
    elif isinstance(result, list):
        raise ValueError(f"XPath query returned multiple elements: {result!r}.")
    else:
        node = result

    try:
        return node.text
    except AttributeError:
        return node


def xslt_text_func(func, _name=None):
    """ Registers a XSLT function with all arguments converted into text from
        single elements.

        If multiple elements are returned in an argument, ValueError is raised.

        :param func: Function to be registered or name of registered function
        :param _name: Internal parameter for registering function name
    """
    if not callable(func):
        return functools.partial(xslt_text_func, _name=func)

    @functools.wraps(func)
    def func_with_text(*args):
        # If a method, pass through both self/cls and XSLT context
        start = 2 if isinstance(func, types.MethodType) else 1
        context, user_args = args[:start], args[start:]

        return func(*context, *map(_convert_to_text, user_args))

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


def xslt_transform(data, xslt, **kw):
    """ Transforms a XML file or object with an XSLT object. Keyword arguments
        are used as string parameters within the XSLT transform.
    """
    try:
        xml = et.parse(data)
    except TypeError:
        xml = data
    params = {k: xslt.strparam(v) for k, v in kw.items()}
    try:
        result = xslt(xml, **params)
    except et.XSLTError as err:
        for error_message in getattr(err, "error_log"):
            logger.error(error_message)
        raise
    for message in getattr(xslt, "error_log"):
        logger.debug(message)

    return result


def collect_xml_data(xml_data):
    """ Collect entries from a XML tree into a dictionary of models and entries.

        Each element within the root are expected to have the same name as
        models.
    """
    # Python >=3.7 guarantees dict is ordered by insertion
    collected = {}
    for element in xml_data.getroot():
        try:
            model = getattr(models, element.tag)
        except AttributeError:
            raise ValueError(f"Element {element} does not match an existing "
                             f"model name.")
        if model not in collected:
            collected[model] = []
        collected[model].append(xml_as_dict(element))

    return collected


def truncate(connection, table, cascade=True):
    """ Deletes data from a table using `TRUNCATE`. """
    statement = (
        psycopg2.sql.SQL("TRUNCATE {} CASCADE" if cascade else "TRUNCATE {}")
        .format(psycopg2.sql.Identifier(table.name))
    )

    with connection.connection.cursor() as cursor:
        cursor.execute(statement)


def acquire_table_lock(connection, table, mode=None):
    """ Executes ``LOCK TABLE ...`` for a table in a transaction. """
    if not connection.in_transaction():
        raise RuntimeError("LOCK requires a running transaction.")

    modes = [
        "ACCESS SHARE",
        "ROW SHARE",
        "ROW EXCLUSIVE",
        "SHARE UPDATE EXCLUSIVE"
        "SHARE",
        "SHARE ROW EXCLUSIVE",
        "EXCLUSIVE",
        "ACCESS EXCLUSIVE",
    ]
    index = modes.index(mode.upper() if mode else "ACCESS EXCLUSIVE")
    statement = (
        psycopg2.sql.SQL("LOCK TABLE {} IN " + modes[index] + " MODE")
        .format(psycopg2.sql.Identifier(table.name))
    )

    with connection.connection.cursor() as cursor:
        cursor.execute(statement)


def lock_all_tables(connection, mode=None):
    for m in models.iter_models():
        acquire_table_lock(connection, m.__table__, mode)


def _iter_every(iterable, length):
    """ Generator for iterable split into lists with maximum length. """
    iterator = iter(iterable)
    section = list(itertools.islice(iterator, length))
    while section:
        yield section
        section = list(itertools.islice(iterator, length))


def _copy_executor(table, null_value):
    statement = (
        psycopg2.sql.SQL("COPY {} FROM STDIN WITH CSV HEADER NULL {}")
        .format(
            psycopg2.sql.Identifier(table.name),
            psycopg2.sql.Literal(null_value)
        )
    )

    def execute_copy(cursor, file_):
        try:
            cursor.copy_expert(statement, file_)
        except Exception:
            logger.error("Error with COPY", exc_info=1)
            error_path = os.path.join(
                current_app.config["TEMP_DIRECTORY"],
                "error_data"
            )
            with open(error_path, "w") as error_f:
                file_.seek(0)
                shutil.copyfileobj(file_, error_f)
                logger.info(f"Data written to {error_path!r}")
            raise

    return execute_copy


def _copy(connection, table, entries):
    """ Copies entries to a table using the COPY command via CSV files. """
    columns = [c.name for c in table.columns]
    null = "\\N"
    copy = _copy_executor(table, null)

    # Convert None values to a set value as to distinguish from empty strings
    def convert_null(row):
        return {c: row[c] if row.get(c) is not None else null
                for c in columns}

    if len(entries) < ROW_LIMIT:
        # newline="" required to make CSV writing work
        buf = io.StringIO(newline="")
        data = csv.DictWriter(buf, columns)
        data.writeheader()
        data.writerows(map(convert_null, entries))
        buf.seek(0)
        with connection.connection.cursor() as cursor:
            copy(cursor, buf)

    else:
        paths = []
        try:
            for section in _iter_every(entries, ROW_LIMIT):
                fd, path = tempfile.mkstemp()
                paths.append(path)
                # newline="" required to make CSV writing work
                with open(fd, "w", newline="") as buf:
                    data = csv.DictWriter(buf, columns)
                    data.writeheader()
                    data.writerows(map(convert_null, section))

            with connection.connection.cursor() as cursor:
                for path in paths:
                    logger.debug(f"Copying {len(entries)} rows to {table.name} "
                                 f"from files {path!r}")
                    with open(path, "r") as buf:
                        copy(cursor, buf)
        finally:
            for path in paths:
                os.remove(path)


def _temp_table_name(table):
    return table.name + "_temp"


def _temp_table(metadata, table):
    """ Creates a temporary table from an existing table. """
    new_columns = (db.Column(c.name, c.type, autoincrement=False)
                   for c in table.columns if not c.autoincrement)

    return db.Table(
        _temp_table_name(table),
        metadata,
        *new_columns,
        prefixes=["TEMPORARY"],
        postgresql_on_commit="DROP"
    )


def _populate_table(connection, metadata, model, entries, overwrite=False,
                    delete_first=False):
    """ Fills a table with data by using COPY and an intermediate table so a
        ON CONFLICT clause can be used.
    """
    if not entries:
        return

    table = metadata.tables[model.__table__.name]
    new_name = _temp_table_name(table)
    if new_name in metadata.tables:
        temp_table = metadata.tables[new_name]
    else:
        temp_table = _temp_table(metadata, table)

    with connection.begin():
        temp_table.create(connection, checkfirst=True)
        truncate(connection, temp_table)

        if delete_first:
            logger.debug(f"Truncating table {table.name}")
            truncate(connection, table)

        logger.debug(f"Copying {len(entries)} rows to table {table.name} via "
                     f"{temp_table.name}")
        # Add entries to temporary table using COPY
        _copy(connection, temp_table, entries)
        # Insert entries from temporary table into main table avoiding conflicts
        insert = (
            postgresql.insert(table)
            .from_select([c.name for c in temp_table.columns],
                         db.select([temp_table]))
        )
        if overwrite and not delete_first:
            p_key = table.primary_key.name
            cols = {c.name: getattr(insert.excluded, c.name)
                    for c in temp_table.columns}
            insert = insert.on_conflict_do_update(constraint=p_key, set_=cols)
        else:
            insert = insert.on_conflict_do_nothing()

        connection.execute(insert)


def populate_database(connection, data, metadata=None, overwrite=False,
                      delete=False, exclude=None):
    """ Populates the database using a dictionary of models and lists of
        entries.
    """
    if not data:
        return

    metadata_ = reflect_metadata(connection) if metadata is None else metadata
    with connection.begin():
        for model, entries in data.items():
            del_ = delete and (exclude is None or model not in exclude)
            _populate_table(connection, metadata_, model, entries, overwrite,
                            del_)
