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

    ATCO_CODES = 'all'
    TRANSPORT_API_ACTIVE = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestConfig(Config):
    DEBUG = True
    TESTING = True


class TestConfigYorkshire(object):
    DEBUG = True
    TESTING = True
    ATCO_CODES = [370, 450]
