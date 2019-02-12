"""
Populate service operators with the NOC dataset.
"""
import os
import re

import lxml.etree as et

from definitions import ROOT_DIR
from nextbus import models
from nextbus.populate import file_ops, utils


NOC_URL = r"https://www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml"
NOC_XSLT = r"nextbus/populate/noc.xslt"
NOC_XML = r"temp/noc_data.xml"

REGEX_OP_WEBSITE = re.compile(r"^[^#]*#(.+)#[^#]*$")


def download_noc_data():
    """ Downloads NOC data as a XML file. """
    return file_ops.download(NOC_URL, directory="temp")


@utils.xslt_text_func
def format_website(_, text):
    """ Retrieves website enclosed by # signs. """
    match = REGEX_OP_WEBSITE.search(text)

    return match.group(1) if match else ""


def _get_noc_data(noc_file, debug=False):
    """ Parses NOC data and transforms with XSLT.

        :param noc_file: File-like object or path for a XML file
        :param debug: Log all messages output from XSLT
        :returns: Transformed data as a XML ElementTree object
    """
    utils.logger.info("Opening NOC XML file %r" % noc_file)
    try:
        data = et.parse(noc_file)
    except (UnicodeDecodeError, et.XMLSyntaxError):
        # NOC data is encoded in Windows-1252 or Latin-1 for some reason
        utils.logger.warning("NOC XML file %r cannot be parsed with UTF-8 - "
                             "trying again with Latin1" % noc_file)
        data = et.parse(noc_file, et.XMLParser(encoding="Latin1"))

    transform = et.XSLT(et.parse(os.path.join(ROOT_DIR, NOC_XSLT)))
    try:
        new_data = transform(data)
    except (et.XSLTParseError, et.XSLTApplyError) as err:
        for error_message in getattr(err, "error_log"):
            utils.logger.error(error_message)
        raise

    if debug:
        utils.logger.debug(getattr(transform, "error_log"))

    return new_data


def commit_noc_data(file_=None):
    """ Convert NOC data (service operators) to database objects and commit them
        to the application database.

        :param file_: Path to raw data in XML form
    """
    path = download_noc_data() if file_ is None else file_
    new_data = _get_noc_data(path)
    noc = utils.PopulateData()
    noc.set_input(new_data)

    noc.add("Operator", models.Operator)
    noc.add("LocalOperator", models.LocalOperator)
    noc.commit(delete=True)

    if file_ is None:
        utils.logger.info("New file %r downloaded; can be deleted" % path)
    utils.logger.info("NOC population done")
