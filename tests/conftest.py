"""
Shared pytest fixtures and functions.
"""
import os

import lxml.etree as et
import pytest

from nextbus import create_app, db, models

from data import TEST_DATA


MAIN = "SQLALCHEMY_DATABASE_URI"
TEST = "TEST_DATABASE_URI"


def _xml_elements_diffs(a, b, _root=None):
    """ Main function for assessing equality of XML elements.

        Goes through each child element recursively, checking each element's
        tag, tail, text and attributes. Returns list of differences and paths
        they are contained in.
    """
    diffs = []
    elem_diffs = []
    # Check tags, text, tails, attributes and number of subelements
    if a.tag != b.tag:
        elem_diffs.append(f"tags: {a.tag!r} != {b.tag!r}")
    if a.text != b.text:
        elem_diffs.append(f"text: {a.text!r} != {b.text!r}")
    if a.tail != b.tail:
        elem_diffs.append(f"tail: {a.tail!r} != {b.tail!r}")
    if a.attrib != b.attrib:
        elem_diffs.append(f"attr: {a.attrib!r} != {b.attrib!r}")
    if len(a) != len(b):
        elem_diffs.append(f"{len(a)} != {len(b)} subelements")
        # Find differences in number of named subelements
        e1_tags = [e.tag for e in a]
        e2_tags = [e.tag for e in b]
        for t in set(e1_tags) | set(e2_tags):
            count = e2_tags.count(t) - e1_tags.count(t)
            if count != 0:
                elem_diffs.append(f"    {count:+d} {t!r}")

    if elem_diffs:
        if _root is not None and a.tag == b.tag:
            within = _root.getpath(a)
        elif _root is not None and a.tag != b.tag:
            within = f"within {_root.getpath(a.getparent())}"
        else:
            within = "within root"
        elem_diffs.insert(0, within)
        diffs.append("\n    ".join(elem_diffs))

    if len(a) > 0 and len(a) == len(b) and a.tag == b.tag:
        # If elements compared have children, iterate through them recursively
        sub_diffs = []
        # Set first element as root when recursing
        root = et.ElementTree(a) if _root is None else _root
        for c, d in zip(a, b):
            sub_diffs.extend(_xml_elements_diffs(c, d, root))
        diffs.extend(sub_diffs)

    if _root is None and diffs:
        diffs.insert(
            0,
            f"{len(diffs):d} difference{'' if len(diffs) == 1 else 's'} found: "
        )

    return diffs


def xml_elements_equal(left, right):
    """ Compares two XML Element objects by iterating through each
        tag recursively and comparing their tags, text, tails and
        attributes.

        A parser to remove blank text between elements is recommended.
    """
    diffs = _xml_elements_diffs(left, right)
    if diffs:
        raise AssertionError("\n\n".join(diffs))


@pytest.fixture(scope="session")
def asserts():
    """ Custom assertion statements. """
    class Asserts:
        xml_elements_equal = xml_elements_equal

    return Asserts


@pytest.fixture(scope="session")
def app():
    """ Creates app during test, using test database URI if applicable. """
    config = os.environ.get("APP_CONFIG")
    os.environ["FLASK_ENV"] = "development"
    if config:
        app = create_app(config_file=config)
    else:
        app = create_app(config_obj="default_config.TestConfig")

    # Find the test database address
    if not app.config.get(TEST):
        raise ValueError(f"{TEST} is not set.")

    if app.config.get(TEST) == app.config.get(MAIN):
        raise ValueError(
            f"The {TEST} and {MAIN} parameters must not be the same; the unit "
            f"tests will commit destructive edits."
        )

    # Set SQLAlchemy database address to test database address
    app.config[MAIN] = app.config.get(TEST)

    assert app.config.get("DEBUG") is True
    assert app.config.get("TESTING") is True

    return app


@pytest.fixture
def with_app(app):
    """ Runs test in application context. """
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """ Runs test client for test. """
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="module")
def db_status():
    class DBStatus:
        def __init__(self):
            self.loaded = False

    return DBStatus()


def _load_db_data():
    """ Loads test data into DB. """
    with db.engine.begin() as connection:
        for table, data in TEST_DATA.items():
            connection.execute(db.metadata.tables[table].insert().values(data))
        models.refresh_derived_models(connection)


@pytest.fixture(scope="module")
def _db_loaded(app, db_status):
    """ Creates DB tables and load data for tests on module level. """
    with app.app_context():
        try:
            db.create_all()
            _load_db_data()
            db_status.loaded = True
            yield
        finally:
            db.session.remove()
            db.drop_all()
            db_status.loaded = False


@pytest.fixture
def db_loaded(_db_loaded):
    """ Runs test with loaded database in separate sessions. """
    try:
        yield _db_loaded
    finally:
        db.session.remove()


@pytest.fixture
def create_db(app, db_status):
    """ Creates DB tables for a test. """
    if db_status.loaded:
        raise Exception("Database is already loaded at the module level.")
    with app.app_context():
        try:
            db.create_all()
            yield
        finally:
            db.session.remove()
            db.drop_all()


@pytest.fixture
def load_db(create_db):
    """ Creates and loads DB data for a test. """
    _load_db_data()
