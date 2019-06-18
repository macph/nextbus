"""
Populate service operators with the NOC dataset.
"""
import os
import re

import lxml.etree as et

from definitions import ROOT_DIR
from nextbus.populate import file_ops, utils


NOC_URL = r"https://www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml"
NOC_XSLT = r"nextbus/populate/noc.xslt"
NOC_XML = r"temp/noc_data.xml"

REGEX_OP_WEBSITE = re.compile(r"^[^#]*#(.+)#[^#]*$")


def download_noc_data():
    """ Downloads NOC data as a XML file. """
    return file_ops.download(NOC_URL, directory="temp")


@utils.xslt_text_func
def scrub_whitespace(_, text):
    """ Replaces all whitespace with a single space each. """
    return " ".join(text.split()) if text is not None else ""


@utils.xslt_text_func
def format_website(_, text):
    """ Retrieves website enclosed by # signs. """
    match = REGEX_OP_WEBSITE.search(text)

    return match.group(1) if match else ""


def commit_noc_data(path=None):
    """ Convert NOC data (service operators) to database objects and commit them
        to the application database.

        :param path: Path to raw data in XML form
    """
    if path is None:
        file_path = file_ops.download(NOC_URL, directory="temp")
    else:
        file_path = path

    utils.logger.info(f"Opening NOC XML file {file_path!r}")
    try:
        data = et.parse(file_path)
    except (UnicodeDecodeError, et.XMLSyntaxError):
        # NOC data is encoded in Windows-1252 for some reason despite the XML
        # declaration specifying UTF-8 encoding
        utils.logger.warning("NOC XML file %r cannot be parsed with UTF-8 - "
                             "trying again with CP1252" % file_path)
        data = et.parse(file_path, et.XMLParser(encoding="CP1252"))

    xslt = et.XSLT(et.parse(os.path.join(ROOT_DIR, NOC_XSLT)))
    utils.populate_database(
        utils.collect_xml_data(utils.xslt_transform(data, xslt)),
        delete=True
    )

    if file_path is None:
        utils.logger.info(f"New file {file_path!r} downloaded; can be deleted")
    utils.logger.info("NOC population done")
