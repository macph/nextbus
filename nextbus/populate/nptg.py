"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
from importlib.resources import open_binary

import lxml.etree as et
from flask import current_app

from nextbus import db, models
from nextbus.populate import file_ops, utils


NPTG_URL = r"http://naptan.app.dft.gov.uk/datarequest/nptg.ashx"


def _remove_districts(connection):
    """ Removes districts without associated localities. """
    orphan_districts = (
        db.select([models.District.code])
        .select_from(
            models.District.__table__
            .outerjoin(models.Locality,
                       models.District.code == models.Locality.district_ref)
        )
        .where(models.Locality.code.is_(None))
        .alias("orphan_districts")
    )

    utils.logger.info("Deleting orphaned districts")
    connection.execute(
        db.delete(models.District.__table__)
        .where(models.District.code.in_(orphan_districts))
    )


def populate_nptg_data(connection, archive=None, list_files=None):
    """ Convert NPTG data (regions admin areas, districts and localities) to
        database objects and commit them to the application database.

        :param connection: Connection & transaction for population
        :param archive: Path to zipped archive file for NPTG XML files.
        :param list_files: List of file paths for NPTG XML files.
    """
    temp = current_app.config.get("TEMP_DIRECTORY")
    if not temp:
        raise ValueError("TEMP_DIRECTORY is not defined.")

    if archive is not None and list_files is not None:
        raise ValueError("Can't specify both archive file and list of files.")
    elif archive is not None:
        iter_files = file_ops.iter_archive(archive)
    elif list_files is not None:
        iter_files = iter(list_files)
    else:
        downloaded = file_ops.download(NPTG_URL, directory=temp,
                                       params={"format": "xml"})
        iter_files = file_ops.iter_archive(downloaded)

    metadata = utils.reflect_metadata(connection)
    with open_binary("nextbus.populate", "nptg.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))

    deleted = False
    for i, file_ in enumerate(iter_files):
        file_name = file_.name if hasattr(file_, "name") else file_
        utils.logger.info(f"Parsing file {file_name!r}")
        utils.populate_database(
            connection,
            utils.collect_xml_data(utils.xslt_transform(file_, xslt)),
            metadata=metadata,
            delete=not deleted
        )
        deleted = True


def process_nptg_data(connection):
    # Remove all orphaned districts
    _remove_districts(connection)
