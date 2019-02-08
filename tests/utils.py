"""
Testing the database.
"""
import datetime
import functools
import os
import types
import unittest

import lxml.etree as et

from definitions import CONFIG_ENV
from nextbus import db, create_app


REGION = {
    "code": "Y",
    "name": "Yorkshire",
    "modified": datetime.datetime.now()
}
ADMIN_AREA = {
    "code": "099",
    "name": "South Yorkshire",
    "atco_code": "370",
    "region_ref": "Y",
    "is_live": True,
    "modified": datetime.datetime.now()
}
DISTRICT = {
    "code": "263",
    "name": "Sheffield",
    "admin_area_ref": "099",
    "modified": datetime.datetime.now()
}
LOCALITY = {
    "code": "E0030518",
    "name": "Sharrow Vale",
    "parent_ref": None,
    "admin_area_ref": "099",
    "district_ref": "263",
    "easting": 433540,
    "northing": 385740,
    "longitude": -1.497413,
    "latitude": 53.36747,
    "modified": datetime.datetime.now()
}
STOP_AREA = {
    "code": "370G100809",
    "name": "Psalter Lane - Bagshot Street",
    "admin_area_ref": "099",
    "locality_ref": "E0030518",
    "stop_area_type": "GPBS",
    "easting": 433794,
    "northing": 385561,
    "longitude": -1.49361482816,
    "latitude": 53.36584531963,
    "modified": datetime.datetime.now()
}
STOP_POINT = {
    "atco_code": "370020602",
    "naptan_code": "37020602",
    "name": "Cherry Tree Road",
    "landmark": "20602",
    "street": "Psalter Lane",
    "crossing": "Cherry Tree Road",
    "indicator": "adj",
    "short_ind": "adj",
    "locality_ref": "E0030518",
    "admin_area_ref": "099",
    "stop_area_ref": "370G100809",
    "easting": 433780,
    "northing": 385542,
    "longitude": -1.49382723113,
    "latitude": 53.36567543456,
    "stop_type": "BCT",
    "bearing": "SW",
    "modified": datetime.datetime.now()
}


def wrap_app_context(func):
    """ Executes the method within a Flask app context. The class instance
        must have a 'app' attribute for a running Flask application.
    """
    @functools.wraps(func)
    def func_within_context(instance, *args, **kwargs):
        with instance.app.app_context():
            return func(instance, *args, **kwargs)

    return func_within_context


class TestAppContext(type):
    """ Metaclass to wrap every method with an app.with_context decorator.

        The following methods are excluded: setUp, setUpClass, tearDown,
        tearDownClass. Static and class methods are also excluded.
    """
    def __new__(mcs, class_name, bases, attributes):
        new_attributes = {}
        excluded = ["setUp", "setUpClass", "tearDown", "tearDownClass"]
        for name, attr in attributes.items():
            if isinstance(attr, types.FunctionType) and name not in excluded:
                new_attributes[name] = wrap_app_context(attr)
            else:
                new_attributes[name] = attr

        return type.__new__(mcs, class_name, bases, new_attributes)


class BaseAppTests(unittest.TestCase, metaclass=TestAppContext):
    """ Base class for testing with the app and database """
    MAIN = "SQLALCHEMY_DATABASE_URI"
    TEST = "TEST_DATABASE_URI"

    @classmethod
    def setUpClass(cls):
        config = os.environ.get(CONFIG_ENV)
        if config:
            cls.app = create_app(config_file=config)
        else:
            cls.app = create_app(config_obj="default_config.DevelopmentConfig")

        # Find the test database address
        if not cls.app.config.get(cls.TEST):
            raise ValueError("No test database URI set in %s" % cls.TEST)

        if cls.app.config.get(cls.TEST) == cls.app.config.get(cls.MAIN):
            raise ValueError("The %s and %s parameters must not be the same; "
                             "the unittests will commit destructive edits."
                             % (cls.TEST, cls.MAIN))

        # Set SQLAlchemy database address to test database address
        cls.app.config[cls.MAIN] = cls.app.config.get(cls.TEST)

    @classmethod
    def tearDownClass(cls):
        del cls.app

    @classmethod
    def create_tables(cls):
        """ Creates tables in database from models. Any errors during
            create_all() are caught and tables dropped
        """
        with cls.app.app_context():
            try:
                db.create_all()
            except:
                db.drop_all()
                raise

    @classmethod
    def drop_tables(cls):
        """ Drops all tables from database """
        with cls.app.app_context():
            # close any connections
            db.session.remove()
            db.drop_all()

    @staticmethod
    def model_as_dict(model_object):
        """ Get all columns and values from a model object as a dict. """
        model = model_object.__class__
        columns = [c.key for c in model.__table__.columns]
        return {c: getattr(model_object, c) for c in columns}


def _xml_elements_equal(e1, e2, _root=None):
    """ Main function for assessing equality of XML elements.

        Goes through each child element recursively, checking each element's
        tag, tail, text and attributes. Returns list of differences and paths
        they are contained in.
    """
    messages = []
    diffs = []
    # Check tags, text, tails, attributes and number of subelements
    if e1.tag != e2.tag:
        diffs.append("tags: %r != %r" % (e1.tag, e2.tag))
    if e1.text != e2.text:
        diffs.append("text: %r != %r" % (e1.text, e2.text))
    if e1.tail != e2.tail:
        diffs.append("tail: %r != %r" % (e1.tail, e2.tail))
    if e1.attrib != e2.attrib:
        diffs.append("attr: %r != %r" % (e1.attrib, e2.attrib))
    if len(e1) != len(e2):
        diffs.append("%d != %d subelements" % (len(e1), len(e2)))
        # Find differences in number of named subelements
        e1_tags = [e.tag for e in e1]
        e2_tags = [e.tag for e in e2]
        diff_count = {e: e2_tags.count(e) - e1_tags.count(e) for e in
                      set(e1_tags) | set(e2_tags)}
        diffs.extend("    %+d %r" % (v, k) for k, v in diff_count.items()
                     if v != 0)

    if diffs:
        if _root is not None and e1.tag == e2.tag:
            diffs.insert(0, _root.getpath(e1))
        elif _root is not None and e1.tag != e2.tag:
            diffs.insert(0, "within %s" % _root.getpath(e1.getparent()))
        else:
            diffs.insert(0, "within root")

        messages.append("\n    ".join(diffs))

    if len(e1) > 0 and len(e1) == len(e2) and e1.tag == e2.tag:
        # If elements compared have children, iterate through them recursively
        sub_diffs = []
        # Set first element as root when recursing
        root = et.ElementTree(e1) if _root is None else _root
        for c1, c2 in zip(e1, e2):
            sub = _xml_elements_equal(c1, c2, root)
            sub_diffs.extend(sub)
        messages.extend(sub_diffs)

    return messages


class BaseXMLTests(unittest.TestCase):
    """ Base tests for comparing XML files. """
    # Use parser which removes blank text from transformed XML files
    parser = et.XMLParser(remove_blank_text=True)

    def assertXMLElementsEqual(self, elem1, elem2, msg=None):
        """ Compares two XML Element objects by iterating through each
            tag recursively and comparing their tags, text, tails and
            attributes.
        """
        diffs = _xml_elements_equal(elem1, elem2)
        if diffs:
            # Raise exception
            count = len(diffs)
            diffs.insert(0, "%d difference%s found: " %
                         (count, "" if count == 1 else "s"))
            new_msg = self._formatMessage(msg, "\n\n".join(diffs))
            raise self.failureException(new_msg)
