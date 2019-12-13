"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
from importlib.resources import open_binary

import lxml.etree as et

from nextbus import db, models
from nextbus.populate import file_ops, utils


NPTG_URL = r"http://naptan.app.dft.gov.uk/datarequest/nptg.ashx"


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
        downloaded = file_ops.download(NPTG_URL, directory="temp",
                                       params={"format": "xml"})
        iter_files = file_ops.iter_archive(downloaded)

    metadata = utils.reflect_metadata()
    with open_binary("nextbus.populate", "nptg.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))

    delete = True
    for file_ in iter_files:
        file_name = file_.name if hasattr(file_, "name") else file_
        utils.logger.info(f"Parsing file {file_name!r}")
        utils.populate_database(
            utils.collect_xml_data(utils.xslt_transform(file_, xslt)),
            metadata=metadata,
            delete=delete
        )
        delete = False

    # Remove all orphaned districts
    _remove_districts()

    if downloaded is not None:
        utils.logger.info(f"New file {downloaded} downloaded; can be deleted")
    utils.logger.info("NPTG population done")
