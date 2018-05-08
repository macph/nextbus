"""
Configuration file for running current version of nextbus.
"""


class Config(object):
    """ Default config. """
    SQLALCHEMY_DATABASE_URI = None  # Location of PostgreSQL database
    TEST_DATABASE_URI = None        # Location of test PostgreSQL database. Must be distinct from
                                    # the above address
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False         # Must be kept False and let all SQLAlchemy queries be logged
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
    MAPBOX_APP_TOKEN = None         # App token to access Mapbox's map service


class DevelopmentConfig(Config):
    """ Config for developing and testing. """
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost/nextbus"
    TEST_DATABASE_URI = "postgresql://localhost/nextbus_test"
    SECRET_KEY = "sup3r sekr3t k3y"
