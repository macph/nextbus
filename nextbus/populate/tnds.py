"""
Populate bus route and timetable data from TNDS.
"""
import ftplib
import os

from flask import current_app
import lxml.etree as et

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, utils


TNDS_URL = r"ftp.tnds.basemap.co.uk"
TNDS_XSLT = r"nextbus/populate/tnds.xslt"


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

    paths = []
    utils.logger.info("Opening FTP connection to %r with credentials" %
                      TNDS_URL)
    with ftplib.FTP(TNDS_URL, user=user, passwd=password) as ftp:
        for region in list_regions:
            file_name = region + ".zip"
            file_path = os.path.join(ROOT_DIR, "temp", file_name)
            utils.logger.info("Downloading file %r from %r" %
                              (file_name, TNDS_URL))
            with open(file_path, "wb") as file_:
                ftp.retrbinary("RETR " + file_name, file_.write)

    return paths


def _get_tnds_transform(region):
    """ Uses XSLT to convert TNDS XML data into several separate datasets. """
    tnds_xslt = et.parse(os.path.join(ROOT_DIR, TNDS_XSLT))
    xsl_ns = {"xsl": tnds_xslt.xpath("namespace-uri(.)")}
    region_param = tnds_xslt.xpath("//xsl:param[@name='region']",
                                   namespaces=xsl_ns)[0]
    region_param.text = region
    transform = et.XSLT(tnds_xslt)

    return transform


def commit_tnds_data(archive=None):
    """ Commits TNDS data to database. """
    list_archives = download_tnds_files() if archive is None else [archive]

    for archive in list_archives:
        transform = _get_tnds_transform("Y")
        for file_ in file_ops.iter_archive(archive):
            data = et.parse(file_)
            try:
                new_data = transform(data)
            except et.XSLTApplyError as err:
                utils.logger.error(err.error_log)
                raise
            new_data.write(os.path.join(ROOT_DIR, "temp/Y", file_.name), pretty_print=True)
