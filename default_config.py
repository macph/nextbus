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
    PERMANENT_SESSION_LIFETIME = 365 * 24 * 60 * 60
                                    # Time to expire if cookie is permanent (1 year)
    SESSION_REFRESH_EACH_REQUEST = False
                                    # With permanent cookie, only update if necessary

    GEOLOCATION_ENABLED = False     # Enables geolocation on webpages, which requires HTTPS
    TRANSPORT_API_ACTIVE = False    # Requests data from API if True, else use local sample for
                                    # testing
    TRANSPORT_API_ID = None         # ID for Transport API
    TRANSPORT_API_KEY = None        # Key for Transport API
    CAMDEN_APP_TOKEN = None         # App token to access Camden's NSPL API; only required to
                                    # bypass throtting limits
    TNDS_USERNAME = None            # FTP username password for TNDS files
    TNDS_PASSWORD = None            # FTP access password for TNDS files


class DevelopmentConfig(Config):
    """ Config for developing. """
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost/nextbus"
    SECRET_KEY = "sup3r sekr3t k3y"
    GEOLOCATION_ENABLED = True


class TestConfig(DevelopmentConfig):
    """ Config for testing. """
    TEST_DATABASE_URI = "postgresql://localhost/nextbus_test"
    TESTING = True
