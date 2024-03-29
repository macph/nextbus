"""
Populate service operators with the NOC dataset.
"""
from importlib.resources import open_binary
import re

import lxml.etree as et
from flask import current_app

from nextbus.populate import file_ops, utils


NOC_URL = r"https://www.travelinedata.org.uk/noc/api/1.0/nocrecords.xml"

REGEX_OP_WEBSITE = re.compile(r"^[^#]*#(.+)#[^#]*$")


@utils.xslt_text_func
def scrub_whitespace(_, text):
    """ Replaces all whitespace with a single space each. """
    return " ".join(text.split()) if text is not None else ""


@utils.xslt_text_func
def format_website(_, text):
    """ Retrieves website enclosed by # signs. """
    match = REGEX_OP_WEBSITE.search(text)

    return match.group(1) if match else ""


def populate_noc_data(connection, path=None):
    """ Convert NOC data (service operators) to database objects and commit them
        to the application database.

        :param connection: Connection for population.
        :param path: Path to raw data in XML form
    """
    temp = current_app.config.get("TEMP_DIRECTORY")
    if not temp:
        raise ValueError("TEMP_DIRECTORY is not defined.")

    if path is None:
        file_path = file_ops.download(NOC_URL, directory=temp)
    else:
        file_path = path

    utils.logger.info(f"Opening NOC XML file {file_path!r}")
    try:
        data = et.parse(file_path)
    except (UnicodeDecodeError, et.XMLSyntaxError):
        # NOC data is encoded in Windows-1252 for some reason despite the XML
        # declaration specifying UTF-8 encoding
        utils.logger.warning(
            f"NOC XML file {file_path!r} cannot be parsed with UTF-8 - trying "
            f"again with CP1252"
        )
        data = et.parse(file_path, et.XMLParser(encoding="CP1252"))

    with open_binary("nextbus.populate", "noc.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))

    utils.populate_database(
        connection,
        utils.collect_xml_data(utils.xslt_transform(data, xslt)),
        delete=True
    )

    if file_path is None:
        utils.logger.info(f"New file {file_path!r} downloaded; can be deleted")
    utils.logger.info("NOC population done")
