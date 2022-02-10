"""
Logging tools for the nextbus package.
"""
import logging
import os
import sys

app_logger = logging.getLogger("nextbus")


class _FilterSQLLog(logging.Filter):
    """ Filter out all INFO records for SQLAlchemy logs.

        This helps prevent clutter in the console, for example not showing INFO
        records for SQL queries even though the console handler has already
        been set to INFO.
    """
    def filter(self, record):
        return not (
            "sqlalchemy.engine" in record.name
            and record.levelno < logging.WARNING
        )


BRIEF = logging.Formatter(
    "%(asctime)s [%(name)s] [%(levelname)s] %(message)s"
)
PRECISE = logging.Formatter(
    "%(asctime)s [%(name)s] [%(levelname)s] [%(module)s:%(lineno)s] "
    "%(message)s"
)


def _set_prod_logging():
    logging.root.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(BRIEF)
    console_handler.setLevel(logging.INFO)
    logging.root.addHandler(console_handler)


def _set_debug_logging(location):
    # Set up SQLAlchemy to log all queries
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.root.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(BRIEF)
    console_handler.setLevel(logging.DEBUG)
    logging.root.addHandler(console_handler)

    if location is not None:
        log_file = os.path.join(location, "nxb_debug.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(PRECISE)
        file_handler.setLevel(logging.DEBUG)
        file_handler.addFilter(_FilterSQLLog())
        logging.root.addHandler(file_handler)


def load_config(app):
    """ Loads configuration for root and other loggers, depending on if the
        'ENV' flag was set to 'production' or 'development'.
    """
    if app.config.get("ENV") != "development":
        _set_prod_logging()
    else:
        _set_debug_logging(app.config.get("LOG_DIRECTORY"))
