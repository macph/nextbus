"""
Configuration file for running current version of nextbus.
"""
import os
from definitions import ROOT_DIR


class Config(object):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = ('sqlite:///' + os.path.join(ROOT_DIR, 'nextbus.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    SECRET_KEY = "sup3r sekr3t k3y"

    # Filters ATCO areas when populating, either 'all' or a list of integer codes
    ATCO_CODES = 'all'
    # Requests data from API if True, else use local sample for testing
    TRANSPORT_API_ACTIVE = False
    # ID for Transport API
    TRANSPORT_API_ID = None
    # Key for Transport API
    TRANSPORT_API_KEY = None
    # App token to access Camden's NSPL API; only required to bypass throtting limits
    CAMDEN_APP_TOKEN = None


class DevelopmentConfig(Config):
    DEBUG = True


class TestConfig(Config):
    DEBUG = True
    TESTING = True


class TestConfigYorkshire(object):
    DEBUG = True
    TESTING = True
    ATCO_CODES = [370, 450]
