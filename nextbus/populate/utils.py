"""
Utilities for the populate subpackage.
"""
import collections
import contextlib
import functools
import logging

from flask import current_app
import lxml.etree as et
import sqlalchemy.dialects.postgresql as pg_sql

from nextbus import db, logger


NXB_EXT_URI = r"http://nextbus.org/functions"

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
        raise
    finally:
        db.session.remove()


def merge_xml(iter_files, parser=None):
    """ Merges multiple XML files with the same structure.

        All XML files are assumed to have the same root element and namespace,
        the same shared subelements, and these subelements contain lists of
        subelements with the same names and structures.

        :param iter_files: Iterator for list of file-like objects or file paths
        (both are accepted by the XML parser).
        :param parser: XML parser - if None the default parser is used
        :returns: Merged XML data as ``et.ElementTree`` object
    """
    first_file = next(iter_files)
    data = et.parse(first_file, parser=parser)
    root = data.getroot()
    ns_ = {"x": data.xpath("namespace-uri(.)")}

    # Iterate over the rest
    for file_ in iter_files:
        new_data = et.parse(file_, parser=parser)
        new_root = new_data.getroot()
        new_uri = new_data.xpath("namespace-uri(.)")
        if new_root.tag != root.tag or new_uri != ns_["x"]:
            raise ValueError("XML files %r and %r do not have the same root "
                             "or namespace." % (first_file, file_))
        for sub_element in new_root:
            # Strip namespace from tag if one exists
            tag = sub_element.tag.split("}")[-1]
            existing = root.xpath("x:" + tag, namespaces=ns_)
            if existing:
                existing[0].extend(sub_element)
            else:
                root.append(sub_element)

    return data


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
    def _function_with_text(instance, context, result, *args, **kwargs):
        if len(result) == 1:
            try:
                text = result[0].text
            except AttributeError:
                text = str(result[0])
            return func(instance, context, text, *args, **kwargs)
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
    def __init__(self, xml_data):
        self.data = et.parse(xml_data)
        self.entries = collections.OrderedDict()
        self.conflicts = {}

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
        # Find all elements matching query
        list_elements = self.data.xpath(xpath_query)
        # Assuming keys in every entry are equal
        columns = xml_as_dict(list_elements[0]).keys()

        # Check indices and add them for INSERT ON CONFLICT statements
        if indices is not None:
            self.conflicts[model] = {"indices": indices, "columns": columns}

        new_entries = self.entries.setdefault(model, [])
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

    def _create_insert_statement(self, model):
        """ Creates an insert statement, depending on whether constraints or
            indices were added.

            :param model: Database model
            :returns: Insert statement to be used by the session.execute()
            function. Values are not included as the execute
            function will add them
        """
        table = model.__table__
        if not self.conflicts.get(model):
            # A simple INSERT statement
            statement = table.insert()
        else:
            # Indices have been specified; make a INSERT ON CONFLICT DO UPDATE
            # statement
            insert = pg_sql.insert(table)
            # Create arguments, add index elements or constraints
            # 'excluded' is a specific property used in ON CONFLICT statements
            # referring to the inserted row conflicting with an existing row
            statement = insert.on_conflict_do_update(
                set_={c: getattr(insert.excluded, c) for c in
                      self.conflicts[model]["columns"]},
                where=table.c.modified < insert.excluded.modified,
                index_elements=self.conflicts[model]["indices"]
            )

        return statement

    def commit(self):
        """ Commits all entries to database. """
        if not self.entries:
            raise ValueError("No data have been added yet.")
        with database_session():
            for model, data in self.entries.items():
                # Delete existing rows
                logger.info("Deleting old %s objects" % model.__name__)
                db.session.execute(model.__table__.delete())
                # Add new rows
                logger.info(
                    "Inserting %d %s object%s into database" %
                    (len(data), model.__name__, "" if len(data) == 1 else "s")
                )
                db.session.execute(self._create_insert_statement(model), data)
