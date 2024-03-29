"""
Populate postcode data from NSPL.
"""
import json

from flask import current_app

from nextbus import models
from nextbus.populate import file_ops, utils


NSPL_API = r"https://opendata.camden.gov.uk/resource/ry6e-hbqy.json"

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


def _download_nspl_data():
    """ Downloads NSPL data from Camden's Socrata API. Requires an app token,
        which can be obtained from Camden's open data site. For more info, see
        https://dev.socrata.com/foundry/opendata.camden.gov.uk/ry6e-hbqy

        The `CAMDEN_API_TOKEN` key in application config is used for access,
        and while it is not necessary it will raise throttling limits on access
        to the API.
    """

    temp = current_app.config.get("TEMP_DIRECTORY")
    if not temp:
        raise ValueError("TEMP_DIRECTORY is not defined.")

    token = current_app.config.get("CAMDEN_API_TOKEN")
    headers = {"X-App-Token": token} if token is not None else {}
    codes = [f"country_code='{c}'" for c in LIST_COUNTRIES]

    params = {
        "$select": ", ".join(LIST_COLUMNS),
        "$where": f"({' OR '.join(codes)})",
        "$limit": 2000000
    }
    new = file_ops.download(NSPL_API, file_name="nspl.json", directory=temp,
                            headers=headers, params=params)

    return new


def populate_nspl_data(connection, path=None):
    """ Converts NSPL data (postcodes) to database objects and commit them
        to the working database.

        :param connection: Connection for population.
        :param path: Path for JSON file. If None, initiates download from the
        Camden Open Data API.
    """
    nspl_path = _download_nspl_data() if path is None else path

    utils.logger.info(f"Opening file {nspl_path!r}")
    with open(nspl_path, "r") as json_file:
        data = json.load(json_file)

    postcodes = []
    utils.logger.info(f"Parsing {len(data)} postcodes")
    for row in data:
        postcodes.append({
            "index": "".join(row["postcode_3"].split()),
            "text": row["postcode_3"],
            "easting": row["easting"],
            "northing": row["northing"],
            "longitude": row["longitude"],
            "latitude": row["latitude"]
        })

    utils.populate_database(
        connection,
        {models.Postcode: postcodes},
        delete=True
    )

    if path is None:
        utils.logger.info(f"New file {nspl_path!r} downloaded; can be deleted")
    utils.logger.info("NSPL population done.")
