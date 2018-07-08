"""
Populate bus route and timetable data from TNDS.
"""
import datetime
import ftplib
import os
import re

from flask import current_app

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate.utils import logger


TNDS_URL = r"ftp.tnds.basemap.co.uk"


def download_tnds_files():
    """ Download TNDS files from FTP server. """
    user = current_app.config.get("TNDS_USERNAME")
    password = current_app.config.get("TNDS_PASSWORD")
    if not user or not password:
        raise ValueError("The application config requires an username and "
                         "password to access the TNDS FTP server. See the "
                         "Traveline website for more details.")

    # Get all region codes to iterate over - not GB
    query_regions = (db.session.query(models.Region.code)
                     .filter(models.Region.code != "GB"))
    list_regions = [r[0] for r in query_regions.all()]
    if not list_regions:
        raise ValueError("NPTG data not populated yet.")

    logger.info("Opening FTP connection to %r with credentials" % TNDS_URL)
    with ftplib.FTP(TNDS_URL, user=user, passwd=password) as ftp:
        for region in list_regions:
            file_name = region + ".zip"
            file_path = os.path.join(ROOT_DIR, "temp", file_name)
            logger.info("Downloading file %r from %r" % (file_name, TNDS_URL))
            with open(file_path, "wb") as file_:
                ftp.retrbinary("RETR " + file_name, file_.write)


PARSE_DURATION = re.compile(
    r"^(|[-+])P(?=.+)(?:(?:)|(\d+)Y)(?:(?:)|(\d+)M)(?:(?:)|(\d+)D)"
    r"(?:T?(?:)(?:)(?:)|T(?:(?:)|(\d+)H)(?:(?:)|(\d+)M)"
    r"(?:(?:)|(\d*\.?\d+|\d+\.?\d*)S))$"
)


def convert_duration(duration, ignore=False):
    """ Converts a time duration from XML data to a timedelta object.

        If the 'ignore' parameter is set to False, specifying a year or month
        value other than zero will raise an exception as they cannot be used
        without context.

        :param duration: Duration value obtained from XML element
        :param ignore: If True, will ignore non zero year or month values
        instead of raising exception
        :returns: timedelta object
    """
    match = PARSE_DURATION.match(duration)
    if not match:
        raise ValueError("Parsing %r failed - not a valid XML duration value."
                         % duration)

    if not ignore and any(i is not None and int(i) != 0 for i in
                          [match.group(2), match.group(3)]):
        raise ValueError("Year and month values cannot be used in timedelta "
                         "objects - they need context.")

    def convert(group, func):
        return func(group) if group is not None else 0

    delta = datetime.timedelta(
        days=convert(match.group(4), int),
        hours=convert(match.group(5), int),
        minutes=convert(match.group(6), int),
        seconds=convert(match.group(7), float)
    )

    if match.group(1) == '-':
        delta *= -1

    return delta


def commit_tnds_data(archives=None):
    """ Commits TNDS data to database. """

    return
