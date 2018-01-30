"""
Configuration file for running current version of nextbus.
"""


class Config(object):
    """ Default config. """
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = None  # Location of PostgreSQL database
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False         # SQL queries not logged (default)
    WTF_CSRF_ENABLED = True         # Enables CSRF in WTForms objects
    SECRET_KEY = None               # A different secret key must be set in production
    ATCO_CODES = "all"              # Filters ATCO areas when populating, either 'all' or a list
                                    # of integer codes
    TRANSPORT_API_ACTIVE = False    # Requests data from API if True, else use local sample for
                                    # testing
    TRANSPORT_API_ID = None         # ID for Transport API
    TRANSPORT_API_KEY = None        # Key for Transport API
    CAMDEN_APP_TOKEN = None         # App token to access Camden's NSPL API; only required to
                                    # bypass throtting limits


class DevelopmentConfig(Config):
    """ Config for developing. All SQL queries are logged. """
    SQLALCHEMY_DATABASE_URI = "postgres://localhost/nextbus"
    SECRET_KEY = "sup3r sekr3t k3y"
    DEBUG = True
    SQLALCHEMY_ECHO = True


class TestConfig(Config):
    """ Config for testing. """
    SQLALCHEMY_DATABASE_URI = "postgres://localhost/nextbus_test"
    SECRET_KEY = "sup3r sekr3t k3y"
    DEBUG = True
    TESTING = True
    SQLALCHEMY_ECHO = True


class TestConfigYorkshire(object):
    """ Config for testing populating from two admin areas only. """
    SQLALCHEMY_DATABASE_URI = "postgres://localhost/nextbus_test"
    SECRET_KEY = "sup3r sekr3t k3y"
    DEBUG = True
    TESTING = True
    ATCO_CODES = [370, 450]
