"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import os

import dateutil.parser as dp
import lxml.etree as et

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, utils

NPTG_URL = r"http://naptan.app.dft.gov.uk/datarequest/nptg.ashx"
NPTG_XSLT = r"nextbus/populate/nptg.xslt"
NPTG_XML = r"temp/nptg_data.xml"


def download_nptg_data():
    """ Downloads NPTG data from the DfT. Comes in a zipped file.
    """
    params = {"format": "xml"}
    new = file_ops.download(NPTG_URL, directory="temp", params=params)

    return new


def _remove_districts():
    """ Removes districts without associated localities. """
    query_districts = (
        db.session.query(models.District.code)
        .outerjoin(models.District.localities)
        .filter(models.Locality.code.is_(None))
        .subquery()
    )

    with utils.database_session():
        utils.logger.info("Deleting orphaned districts")
        query = (
            models.District.query
            .filter(models.District.code.in_(query_districts))
        )
        query.delete(synchronize_session="fetch")


def _get_nptg_data(nptg_file):
    """ Parses NPTG XML data, getting lists of regions, administrative areas,
        districts and localities.

        :param nptg_file: File-like object or path for a XML file
        :returns: Transformed data as a XML ElementTree object
    """
    utils.logger.info("Opening NPTG files")
    data = et.parse(nptg_file)
    xslt_data = et.parse(os.path.join(ROOT_DIR, NPTG_XSLT))

    transform = et.XSLT(xslt_data)
    try:
        new_data = transform(data)
    except (et.XSLTParseError, et.XSLTApplyError) as err:
        for error_message in getattr(err, "error_log"):
            utils.logger.error(error_message)
        raise

    return new_data


def commit_nptg_data(archive=None, list_files=None):
    """ Convert NPTG data (regions admin areas, districts and localities) to
        database objects and commit them to the application database.

        :param archive: Path to zipped archive file for NPTG XML files.
        :param list_files: List of file paths for NPTG XML files.
    """
    downloaded = None
    if archive is not None and list_files is not None:
        raise ValueError("Can't specify both archive file and list of files.")
    elif archive is not None:
        iter_files = file_ops.iter_archive(archive)
    elif list_files is not None:
        iter_files = iter(list_files)
    else:
        downloaded = download_nptg_data()
        iter_files = file_ops.iter_archive(downloaded)

    # Go through data and create objects for committing to database
    nptg = utils.PopulateData()
    for file_ in iter_files:
        file_name = file_.name if hasattr(file_, "name") else file_
        utils.logger.info("Parsing file %r" % file_name)
        nptg.add_from(_get_nptg_data(file_))

    nptg.commit(delete=True)
    # Remove all orphaned districts
    _remove_districts()

    if downloaded is not None:
        utils.logger.info("New file %r downloaded; can be deleted" % downloaded)
    utils.logger.info("NPTG population done")
