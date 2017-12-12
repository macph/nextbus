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
        la_file = os.path.join(ROOT_DIR, "nextbus/populate/local_authorities.json")
        with open(la_file, 'r') as laf:
            list_la = [local_auth['la_code'] for local_auth in json.load(laf)
                       if int(local_auth['atco_area_code']) in atco_codes]
        codes = ["local_authority_code='%s'" % la for la in list_la]
    else:
        codes = ["country_code='%s'" % c for c in LIST_COUNTRIES]

    params = {
        '$select': ', '.join(LIST_COLUMNS),
        '$where': '(%s) AND (%s)' % (' OR '.join(codes), 'positional_quality < 8'),
        '$limit': 2000000
    }
    new = file_ops.download(NSPL_API, "nspl.json", os.path.join(ROOT_DIR, "temp"),
                            headers=headers, params=params)

    return new


class _NSPLData(object):
    """ Helper class for processing NSPL postcode data. """
    la_file = os.path.join(ROOT_DIR, "nextbus/populate/local_authorities.json")

    def __init__(self, atco_codes):
        self.local_auth = {}
        with open(self.la_file, 'r') as laf:
            for local_auth in json.load(laf):
                if not atco_codes or local_auth["atco_area_code"] in atco_codes:
                    self.local_auth[local_auth.pop("la_code")] = local_auth

    def __call__(self, row):
        local_authority = self.local_auth[row["local_authority_code"]]
        dict_postcode = {
            'index':                ''.join(row['postcode_3'].split()),
            'text':                 row['postcode_3'],
            'local_authority_code': row['local_authority_code'],
            'admin_area_code':      local_authority['admin_area_code'],
            'district_code':        local_authority['district_code'],
            'easting':              row['easting'],
            'northing':             row['northing'],
            'longitude':            row['longitude'],
            'latitude':             row['latitude']
        }
        return models.Postcode(**dict_postcode)


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
        click.echo("Downloading NSPL data...")
        nspl_path = download_nspl_data(atco_codes)
    else:
        nspl_path = nspl_file

    click.echo("Opening file %r..." % nspl_path)
    with open(nspl_path, 'r') as json_file:
        data = json.load(json_file)
        list_postcodes = []
    parse_psc = _NSPLData(atco_codes)
    with progress_bar(data, label="Parsing postcode data") as iter_postcodes:
        for row in iter_postcodes:
            list_postcodes.append(parse_psc(row))

    try:
        db.session.begin()
        click.echo("Deleting old records...")
        models.Postcode.query.delete()
        click.echo("Adding %d postcodes..." % len(list_postcodes))
        db.session.add_all(list_postcodes)
        click.echo("Committing changes to database...")
        db.session.commit()
    except:
        db.session.rollback()
        raise

    if nspl_file is None:
        click.echo("NSPL population done. The file 'nspl.json' is saved in "
                   "the Temp directory.")
    else:
        click.echo("NSPL population done.")


if __name__ == "__main__":
    NSPL = os.path.join(ROOT_DIR, "temp/nspl.csv")
    with current_app.app_context():
        commit_nspl_data(nspl_file=NSPL)
