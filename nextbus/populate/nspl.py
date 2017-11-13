"""
Populate postcode data from NSPL.
"""
import os
import json
import datetime
import dateutil.parser
import click
from flask import current_app

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, IterChunk, progress_bar


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
    new, info = file_ops.download(NSPL_API, "nspl.json", os.path.join(ROOT_DIR, "temp"),
                                  headers=headers, params=params)
    str_last_modified = info.get('Last-Modified')
    if str_last_modified is not None:
        tzi = {'GMT': datetime.timezone.utc}
        dt_modified = dateutil.parser.parse(str_last_modified, tzinfos=tzi)
    else:
        dt_modified = None

    return new, dt_modified


class _NSPLData(object):
    """ Helper class for processing NSPL postcode data. """
    def __init__(self, atco_codes, dict_local_auth):
        self.atco_codes = atco_codes
        self.local_auth = dict_local_auth

    def __call__(self, rows):
        list_objects = []
        for row in rows:
            local_authority = self.local_auth[row["Local Authority Code"]]
            dict_psc = {
                "postcode":             row["Postcode 3"],
                "postcode_2":           ''.join(row["Postcode 3"].split()),
                "local_authority_code": row["Local Authority Code"],
                "admin_area_code":      local_authority["admin_area_code"],
                "district_code":        local_authority["district_code"],
                "easting":              row["Easting"],
                "northing":             row["Northing"],
                "longitude":            row["Longitude"],
                "latitude":             row["Latitude"]
            }
            list_objects.append(models.Postcode(**dict_psc))

        return list_objects


def commit_nspl_data(nspl_file=None, atco_codes=None):
    """ Converts NSPL data (postcodes) to database objects and commit them
        to the working database.

        :param nspl_file: Path for JSON file. If None, initiates download from
        the Camden Open Data API.
        :param atco_codes: List of ATCO codes to filter; if None, all areas
        within Great Britain are included.
    """
    meta = models.Meta.query.first()
    if nspl_file is None:
        click.echo("Downloading NSPL data...")
        nspl_path, last_modified = download_nspl_data(atco_codes)
        if meta is not None:
            if meta.nspl_last_modified > last_modified:
                raise ValueError("The existing NSPL data is newer.")
            if last_modified - meta.nspl_last_modified < datetime.timedelta(hours=24):
                raise ValueError("The existing NSPL data is up to date.")
    else:
        last_modified = datetime.datetime.utcnow()
        nspl_path = nspl_file

    dict_la = {}
    la_file = os.path.join(ROOT_DIR, "nextbus/populate/local_authorities.json")
    with open(la_file, 'r') as laf:
        for local_auth in json.load(laf):
            if not atco_codes or int(local_auth["atco_area_code"]) in atco_codes:
                dict_la[local_auth.pop("la_code")] = local_auth

    click.echo("Opening file %r..." % nspl_file)
    with open(nspl_path, 'r') as json_file:
        data = json.load(json_file)
        list_postcodes = []
        with progress_bar(data, label="Parsing postcode data") as iter_postcodes:
            for row in iter_postcodes:
                local_authority = dict_la[row['local_authority_code']]
                dict_psc = {
                    'postcode':             row['postcode_3'],
                    'postcode_2':           ''.join(row['postcode_3'].split()),
                    'local_authority_code': row['local_authority_code'],
                    'admin_area_code':      local_authority['admin_area_code'],
                    'district_code':        local_authority['district_code'],
                    'easting':              row['easting'],
                    'northing':             row['northing'],
                    'longitude':            row['longitude'],
                    'latitude':             row['latitude']
                }
                list_postcodes.append(models.Postcode(**dict_psc))

    try:
        if meta is None:
            db.session.add(models.Meta(nspl_last_modified=last_modified))
        else:
            meta.nspl_last_modified = last_modified
        click.echo("Deleting old records...")
        models.Postcode.query.delete()
        click.echo("Adding %d postcodes..." % len(list_postcodes))
        db.session.add_all(list_postcodes)
        click.echo("Committing changes to database...")
        db.session.commit()
    except:
        db.session.rollback()
        raise


if __name__ == "__main__":
    NSPL = os.path.join(ROOT_DIR, "temp/data/nspl.csv")
    with current_app.app_context():
        commit_nspl_data(nspl_file=NSPL)
