"""
Populate postcode data from NSPL.
"""
import os
import json
import click
from flask import current_app

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, progress_bar


NSPL_API = r"https://opendata.camden.gov.uk/resource/ry6e-hbqy.json"
LA_JSON = r"nextbus/populate/local_authorities.json"

LIST_COLUMNS = [
    'postcode_3',
    'local_authority_code',
    'easting',
    'northing',
    'longitude',
    'latitude'
]

LIST_COUNTRIES = [
    'E92000001',
    'S92000003',
    'W92000004'
]


def download_nspl_data(atco_codes=None, token=None):
    """ Downloads NSPL data from Camden's Socrata API. Requires an app token,
        which can be obtained from Camden's open data site. For more info, see
        https://dev.socrata.com/foundry/opendata.camden.gov.uk/ry6e-hbqy

        :param atco_codes: List of ATCO codes used to filter areas. If None,
        all postcodes in Great Britain (outwith IoM, Channel Islands and
        Northern Ireland) are retrieved.
        :param token: Camden API token for retrieving NSPL data. This keyword
        argument is checked first, then the 'CAMDEN_API_TOKEN' key in Flask
        config, and if both are None no token is used. A token is not really
        necessary but will raise throttling limits on access to the API.
    """
    if token is not None:
        headers = {'X-App-Token': token}
    elif current_app.config.get('CAMDEN_API_TOKEN') is not None:
        headers = {'X-App-Token': current_app.config.get('CAMDEN_API_TOKEN')}
    else:
        headers = {}

    if atco_codes:
        la_file = os.path.join(ROOT_DIR, LA_JSON)
        with open(la_file, 'r') as laf:
            list_la = [local_auth['la_code'] for local_auth in json.load(laf)
                       if int(local_auth['atco_area_code']) in atco_codes]
        codes = ["local_authority_code='%s'" % la for la in list_la]
    else:
        codes = ["country_code='%s'" % c for c in LIST_COUNTRIES]

    params = {
        '$select': ', '.join(LIST_COLUMNS),
        '$where': '(%s) AND (positional_quality < 8)' % ' OR '.join(codes),
        '$limit': 2000000
    }
    new = file_ops.download(NSPL_API, "nspl.json",
                            os.path.join(ROOT_DIR, "temp"),
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
    with open(os.path.join(ROOT_DIR, LA_JSON), 'r') as laf:
        la_data = json.load(laf)
    for row in la_data:
        if not atco_codes or int(row["atco_area_code"]) in atco_codes:
            local_auth[row.pop("la_code")] = row

    return local_auth


def commit_nspl_data(nspl_file=None):
    """ Converts NSPL data (postcodes) to database objects and commit them
        to the working database.

        :param nspl_file: Path for JSON file. If None, initiates download from
        the Camden Open Data API.
    """
    get_atco_codes = current_app.config.get('ATCO_CODES')
    if get_atco_codes != 'all' and not isinstance(get_atco_codes, list):
        raise ValueError("ATCO codes must be set to either 'all' or a list of "
                         "codes to filter.")
    else:
        atco_codes = None if get_atco_codes == 'all' else get_atco_codes

    if nspl_file is None:
        click.echo("Downloading NSPL data from Camden Open Data")
        nspl_path = download_nspl_data(atco_codes)
    else:
        nspl_path = nspl_file

    click.echo("Opening file %r" % nspl_path)
    with open(nspl_path, 'r') as json_file:
        data = json.load(json_file)

    list_postcodes = []
    local_auth = _get_dict_local_auth(atco_codes)
    with progress_bar(data, label="Parsing postcode data") as iter_postcodes:
        for row in iter_postcodes:
            local_authority = local_auth[row["local_authority_code"]]
            dict_postcode = {
                'index':                ''.join(row['postcode_3'].split()),
                'text':                 row['postcode_3'],
                'admin_area_code':      local_authority['admin_area_code'],
                'district_code':        local_authority['district_code'],
                'easting':              row['easting'],
                'northing':             row['northing'],
                'longitude':            row['longitude'],
                'latitude':             row['latitude']
            }
            list_postcodes.append(dict_postcode)

    try:
        click.echo("Deleting old records")
        db.session.execute(models.Postcode.__table__.delete())
        click.echo("Adding %d %s objects to session" %
                   (len(list_postcodes), models.Postcode.__name__))
        db.session.execute(models.Postcode.__table__.insert(), list_postcodes)
        click.echo("Committing changes to database")
        db.session.commit()
    except:
        db.session.rollback()
        raise
    finally:
        db.session.close()

    if nspl_file is None:
        click.echo("NSPL population done. The file 'nspl.json' is saved in "
                   "the Temp directory.")
    else:
        click.echo("NSPL population done.")


if __name__ == "__main__":
    NSPL = os.path.join(ROOT_DIR, "temp/nspl.csv")
    with current_app.app_context():
        commit_nspl_data(nspl_file=NSPL)
