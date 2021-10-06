"""
Configuration file for running current version of nextbus.
"""
import os


class Config(object):
    """ Default config. """
    # Location of PostgreSQL database
    SQLALCHEMY_DATABASE_URI = None
    # Location of test PostgreSQL database. Must be distinct from the above
    # address
    TEST_DATABASE_URI = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Must be kept False and let all SQLAlchemy queries be logged
    SQLALCHEMY_ECHO = False

    ROOT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    # Location of file to dump database to and restore from
    DATABASE_DUMP_PATH = "temp/nextbus.db.dump"

    # Enables CSRF in WTForms objects
    WTF_CSRF_ENABLED = True
    # A different secret key must be set in production
    SECRET_KEY = None
    # Time to expire if cookie is permanent (1 year)
    PERMANENT_SESSION_LIFETIME = 365 * 24 * 60 * 60
    # With permanent cookie, only update if necessary
    SESSION_REFRESH_EACH_REQUEST = False
    # Set same-site policy for cookies as 'Lax'.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Enables geolocation on webpages, which requires HTTPS
    GEOLOCATION_ENABLED = False
    # Requests data from API if True, else use timetabled data
    TRANSPORT_API_ACTIVE = False
    # Set a limit on the number of requests per day starting at 00:00 UTC
    # Further requests will utilise timetabled data. Ignored if negative or None
    TRANSPORT_API_LIMIT = None
    # ID for Transport API
    TRANSPORT_API_ID = None
    # Key for Transport API
    TRANSPORT_API_KEY = None
    # App token to access Camden's NSPL API; only required to bypass throttling
    # limits
    CAMDEN_APP_TOKEN = None
    # FTP username and password for TNDS files
    TNDS_USERNAME = None
    TNDS_PASSWORD = None


class DevelopmentConfig(Config):
    """ Config for developing. """
    SQLALCHEMY_DATABASE_URI = "postgresql://localhost/nextbus"
    SECRET_KEY = "sup3r sekr3t k3y"
    GEOLOCATION_ENABLED = True


class TestConfig(DevelopmentConfig):
    """ Config for testing. """
    TEST_DATABASE_URI = "postgresql://localhost/nextbus_test"
    TESTING = True
