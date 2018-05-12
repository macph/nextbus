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
    """ Downloads NPTG data from the DfT. Comes in a zipped file so the NPTG
        XML file is extracted first.
    """
    params = {"format": "xml"}
    new = file_ops.download(NPTG_URL, directory="temp", params=params)

    return new


def _add_modified_date(area):
    """ Helper function to convert last modified date (as a string) to a
        DateTime object.
    """
    if area.get("modified") is not None:
        area["modified"] = dp.parse(area["modified"])

    return area


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


def _get_nptg_data(nptg_files, atco_codes=None):
    """ Parses NPTG XML data, getting lists of regions, administrative areas,
        districts and localities that fit specified ATCO code (or all of them
        if atco_codes is None).

        :param nptg_files: Iterator for list of NPTG XML files
        :param atco_codes: List of ATCO area codes to filter by, or all of them
        if set to None
        :returns: Transformed data as a XML ElementTree object
    """
    utils.logger.info("Opening NPTG files")
    data = utils.merge_xml(nptg_files)
    names = {"n": data.xpath("namespace-uri(.)")}
    transform = et.parse(os.path.join(ROOT_DIR, NPTG_XSLT))
    ext = et.Extension(utils.XSLTExtFunctions(), None, ns=utils.NXB_EXT_URI)

    if atco_codes:
        # Filter by ATCO area - use NPTG data to find correct admin area codes
        utils.logger.info("Checking ATCO areas")
        admin_areas = []
        invalid_codes = []
        for code in atco_codes:
            area = data.xpath("//n:AdministrativeArea[n:AtcoAreaCode='%s']"
                              % code, namespaces=names)
            if area:
                admin_areas.append(area[0])
            else:
                invalid_codes.append(code)

        if invalid_codes:
            raise ValueError(
                "The following ATCO codes cannot be found: %s."
                % ", ".join(repr(i) for i in invalid_codes)
            )

        area_codes = [area.xpath("n:AdministrativeAreaCode/text()",
                                 namespaces=names)[0]
                      for area in admin_areas]
        area_query = " or ".join(".='%s'" % code for code in area_codes)

        # Create new conditions to attach to XPath queries for filtering
        # administrative areas; for example, can do
        # 'n:Element[condition1][condition2]' instead of
        # 'n:Element[condition1 and condition2]'.
        area_ref = {
            "regions": "[.//n:AdministrativeAreaCode[%s]]" % area_query,
            "areas": "[n:AdministrativeAreaCode[%s]]" % area_query,
            "districts": "[ancestor::n:AdministrativeArea/"
                         "n:AdministrativeAreaCode[%s]]" % area_query,
            "localities": "[n:AdministrativeAreaRef[%s]]" % area_query
        }

        # Modify the XPath queries to filter by admin area
        xsl_names = {"xsl": transform.xpath("namespace-uri(.)")}
        for k, ref in area_ref.items():
            param = transform.xpath("//xsl:param[@name='%s']" % k,
                                    namespaces=xsl_names)[0]
            param.attrib["select"] += ref

    utils.logger.info("Applying XSLT to NPTG data")
    new_data = data.xslt(transform, extensions=ext)

    return new_data


def commit_nptg_data(archive=None, list_files=None):
    """ Convert NPTG data (regions admin areas, districts and localities) to
        database objects and commit them to the application database.

        :param archive: Path to zipped archive file for NPTG XML files.
        :param list_files: List of file paths for NPTG XML files.
    """
    downloaded = None
    atco_codes = utils.get_atco_codes()
    if archive is not None and list_files is not None:
        raise ValueError("Can't specify both archive file and list of files.")
    elif archive is not None:
        iter_files = file_ops.iter_archive(archive)
    elif list_files is not None:
        iter_files = iter(list_files)
    else:
        downloaded = download_nptg_data()
        iter_files = file_ops.iter_archive(downloaded)

    # Transform data and write to temporary file
    new_path = os.path.join(ROOT_DIR, NPTG_XML)
    new_data = _get_nptg_data(iter_files, atco_codes)
    new_data.write_output(new_path)

    # Go through data and create objects for committing to database
    nptg = utils.DBEntries(new_path)
    nptg.add("Regions/Region", models.Region, func=_add_modified_date)
    nptg.add("AdminAreas/AdminArea", models.AdminArea, func=_add_modified_date)
    nptg.add("Districts/District", models.District, func=_add_modified_date)
    nptg.add("Localities/Locality", models.Locality, func=_add_modified_date)
    # Commit changes to database
    nptg.commit()
    # Remove all orphaned districts
    _remove_districts()

    if downloaded is not None:
        utils.logger.info("New file %r downloaded; can be deleted" % downloaded)
    utils.logger.info("NPTG population done")
