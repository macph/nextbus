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
        """ Creates tables in database from models """
        with cls.app.app_context():
            db.create_all()

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


class BaseXMLTests(unittest.TestCase):
    """ Base tests for comparing XML files. """
    # Use parser which removes blank text from transformed XML files
    parser = et.XMLParser(remove_blank_text=True)

    def assertXMLElementsEqual(self, e1, e2, msg=None, _path=None):
        """ Compares two XML Element objects by iterating through each
            tag recursively and comparing their tags, text, tails and
            attributes.
        """
        message = []
        # Check tags, text, tails, attributes and number of subelements
        if e1.tag != e2.tag:
            message.append("Tags %r != %r" % (e1.tag, e2.tag))
        if e1.text != e2.text:
            message.append("Text %r != %r" % (e1.text, e2.text))
        if e1.tail != e2.tail:
            message.append("Tail strings %r != %r" % (e1.tail, e2.tail))
        if e1.attrib != e2.attrib:
            message.append("Attributes %r != %r" % (e1.attrib, e1.attrib))
        if len(e1) != len(e2):
            message.append("%d != %d subelements" % (len(e1), len(e2)))

        # Errors found: create message and raise exception
        if message:
            if _path is not None and e1.tag == e2.tag:
                message.insert(0, "For element %s/%s:" % (_path, e1.tag))
            elif _path is not None and e1.tag != e2.tag:
                message.insert(0, "For subelements within %s:" % _path)

            new_msg = self._formatMessage(msg, "\n".join(message))
            raise self.failureException(new_msg)

        # If elements compared have children, iterate through them recursively
        if len(e1) > 0:
            new_path = e1.tag if _path is None else _path + "/" + e1.tag
            for c1, c2 in zip(e1, e2):
                self.assertXMLElementsEqual(c1, c2, _path=new_path)
