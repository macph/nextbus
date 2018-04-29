"""
Logging tools for the nextbus package.
"""
import logging
import logging.config


def _filter_sqlalchemy_log(level):
    """ Returns a function that filters SQLAlchemy records by setting a higher
        threshold.

        This helps prevent clutter in the console, for example not showing INFO
        records for SQL queries even though the console handler has already
        been set to INFO.
    """
    def filter_sqlalchemy_log(record):
        return not ("sqlalchemy.engine" in record.name
                    and record.levelno < level)

    return filter_sqlalchemy_log


BRIEF = "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
PRECISE = ("[%(asctime)s] [%(name)s] [%(levelname)s] [%(module)s:%(lineno)s] "
           "%(message)s")

PROD_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "brief": {"format": BRIEF},
        "precise": {"format": PRECISE}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler",
                    "formatter": "brief",
                    "level": "INFO"},
        "file":    {"class": "logging.handlers.RotatingFileHandler",
                    "backupCount": 4,
                    "filename": "nxb.log",
                    "formatter": "precise",
                    "level": "INFO",
                    "maxBytes": 2 * 1024 * 1024}
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO"
    }
}

DEBUG_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "sqlalchemy_warn": {"()": _filter_sqlalchemy_log,
                            "level": logging.WARNING}
    },
    "formatters": {
        "brief": {"format": BRIEF},
        "precise": {"format": PRECISE}
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler",
                    "filters": ["sqlalchemy_warn"],
                    "formatter": "brief",
                    "level": "DEBUG"},
        "file":    {"class": "logging.FileHandler",
                    "filename": "nxb_debug.log",
                    "formatter": "precise",
                    "level": "DEBUG",
                    "mode": "w"}
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG"
    }
}


def load_log_config(app):
    """ Loads configuration for root and other loggers, depending on if the
        'ENV' flag was set to 'production' or 'development'.
    """
    if app.config.get("ENV") != "development":
        logging.config.dictConfig(PROD_LOG_CONFIG)
    else:
        # Set up SQLAlchemy to log all queries
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
        logging.config.dictConfig(DEBUG_LOG_CONFIG)
