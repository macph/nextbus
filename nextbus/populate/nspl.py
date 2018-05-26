"""
Populate postcode data from NSPL.
"""
import os
import json
from flask import current_app

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, utils


NSPL_API = r"https://opendata.camden.gov.uk/resource/ry6e-hbqy.json"
LA_JSON = r"nextbus/populate/local_authorities.json"

LIST_COLUMNS = [
    "postcode_3",
    "local_authority_code",
    "easting",
    "northing",
    "longitude",
    "latitude"
]

LIST_COUNTRIES = [
    "E92000001",
    "S92000003",
    "W92000004"
]


def download_nspl_data(atco_codes=None):
    """ Downloads NSPL data from Camden's Socrata API. Requires an app token,
        which can be obtained from Camden's open data site. For more info, see
        https://dev.socrata.com/foundry/opendata.camden.gov.uk/ry6e-hbqy

        The ``CAMDEN_API_TOKEN`` key in application config is used for access,
        and while it is not necessary it will raise throttling limits on access
        to the API.

        :param atco_codes: List of ATCO codes used to filter areas. If None,
        all postcodes in Great Britain (outwith IoM, Channel Islands and
        Northern Ireland) are retrieved.
    """
    token = current_app.config.get("CAMDEN_API_TOKEN")
    headers = {"X-App-Token": token} if token is not None else {}

    if atco_codes:
        codes = []
        cond = "local_authority_code='%s'"
        with open(os.path.join(ROOT_DIR, LA_JSON), "r") as laf:
            for local_auth in json.load(laf):
                if int(local_auth["atco_area_code"]) in atco_codes:
                    codes.append(cond % local_auth["la_code"])
    else:
        codes = ["country_code='%s'" % c for c in LIST_COUNTRIES]

    params = {
        "$select": ", ".join(LIST_COLUMNS),
        "$where": "(%s) AND (positional_quality < 8)" % " OR ".join(codes),
        "$limit": 2000000
    }
    new = file_ops.download(NSPL_API, file_name="nspl.json", directory="temp",
                            headers=headers, params=params)

    return new


def _get_dict_local_auth(atco_codes=None):
    """ Opens JSON file with local authority data and create a dict with local
        authority codes as keys.

        :param atco_codes: List of ATCO codes to filter by, or None to include
        everything
        :returns: Dict with local authority codes as keys
    """
    local_auth = {}
    with open(os.path.join(ROOT_DIR, LA_JSON), "r") as laf:
        la_data = json.load(laf)
    for row in la_data:
        if not atco_codes or int(row["atco_area_code"]) in atco_codes:
            local_auth[row.pop("la_code")] = row

    return local_auth


def commit_nspl_data(file_=None):
    """ Converts NSPL data (postcodes) to database objects and commit them
        to the working database.

        :param file_: Path for JSON file. If None, initiates download from
        the Camden Open Data API.
    """
    atco_codes = current_app.config.get("ATCO_CODES")
    if atco_codes is not None and not isinstance(atco_codes, list):
        raise ValueError("ATCO codes must be set to either None or a list of "
                         "codes to filter.")

    downloaded_file = None
    if file_ is None:
        downloaded_file = download_nspl_data(atco_codes)
        nspl_path = downloaded_file
    else:
        nspl_path = file_

    utils.logger.info("Opening file %r" % nspl_path)
    with open(nspl_path, "r") as json_file:
        data = json.load(json_file)

    list_postcodes = []
    local_auth = _get_dict_local_auth(atco_codes)
    utils.logger.info("Parsing %d postcodes" % len(data))
    for row in data:
        local_authority = local_auth[row["local_authority_code"]]
        dict_postcode = {
            "index":                "".join(row["postcode_3"].split()),
            "text":                 row["postcode_3"],
            "admin_area_ref":       local_authority["admin_area_code"],
            "district_ref":         local_authority["district_code"],
            "easting":              row["easting"],
            "northing":             row["northing"],
            "longitude":            row["longitude"],
            "latitude":             row["latitude"]
        }
        list_postcodes.append(dict_postcode)

    with utils.database_session():
        utils.logger.info("Deleting previous rows")
        db.session.execute(models.Postcode.__table__.delete())
        utils.logger.info("Adding %d %s objects to database" %
                    (len(list_postcodes), models.Postcode.__name__))
        db.session.execute(models.Postcode.__table__.insert(), list_postcodes)

    if downloaded_file is not None:
        utils.logger.info("New file %r downloaded; can be deleted" % downloaded_file)
    utils.logger.info("NSPL population done.")
