"""
Populate postcode data from NSPL.
"""
import os
import csv
import json
import multiprocessing
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
        codes = ["local_authority_code=%s" % la for la in list_la]
    else:
        codes = ["country_code=%s" % c for c in LIST_COUNTRIES]

    params = {
        '$select': ', '.join(LIST_COLUMNS),
        '$where': ' OR '.join(codes),
        '$limit': 2000000
    }
    new = file_ops.download(NSPL_API, "nspl.json", os.path.join(ROOT_DIR, "temp"),
                            headers=headers, params=params)

    return new


class _NSPLData(object):
    """ Helper class for processing NSPL postcode data. """
    def __init__(self, atco_codes, dict_local_auth):
        self.atco_codes = atco_codes
        self.local_auth = dict_local_auth

    def __call__(self, rows):
        list_objects = []
        for row in rows:
            if self.atco_codes and row["Local Authority Code"] not in self.local_auth:
                # Filter by ATCO area code if it applies
                continue
            if row["Country Code"] not in ['E92000001', 'S92000003', 'W92000004']:
                # Don't need NI, IoM or the Channel Islands
                continue
            if row["Positional Quality"] in [8, 9]:
                # Low accuracy; just skip row
                continue
            local_authority = self.local_auth[row["Local Authority Code"]]
            dict_psc = {
                "postcode":             row["Postcode 3"],
                "postcode_2":           ''.join(row["Postcode 3"].split()),
                "local_authority_code": row["Local Authority Code"],
                "admin_area_code":      local_authority["admin_area_code"],
                "district_code":        local_authority["nptg_district_code"],
                "easting":              row["Easting"],
                "northing":             row["Northing"],
                "longitude":            row["Longitude"],
                "latitude":             row["Latitude"]
            }
            list_objects.append(models.Postcode(**dict_psc))

        return list_objects


def commit_nspl_data(nspl_file, atco_codes=None):
    """ Converts NSPL data (postcodes) to database objects and commit them
        to the working database.
    """
    dict_la = {}
    la_file = os.path.join(ROOT_DIR, "nextbus/local_authorities.json")
    with open(la_file, 'r') as laf:
        for local_auth in json.load(laf):
            if not atco_codes or int(local_auth["atco_area_code"]) in atco_codes:
                dict_la[local_auth.pop("la_code")] = local_auth

    click.echo("Opening file %r..." % nspl_file)
    with open(nspl_file, 'r') as csv_file:
        # Find number of rows in CSV file, then reset read position
        len_lines = sum(1 for r in csv.reader(csv_file)) - 1
        csv_file.seek(0)

        chunk_size = 10000
        cores = multiprocessing.cpu_count()
        iter_postcodes = IterChunk(csv.DictReader(csv_file), chunk_size * cores)

        list_postcodes = []
        filter_psc = _NSPLData(atco_codes, dict_la)
        with progress_bar(None, label="Parsing postcode data",
                          length=len_lines) as prog, multiprocessing.Pool(cores) as pool:
            for rows in iter_postcodes:
                pieces = list(IterChunk(iter(rows), chunk_size))
                for piece in pool.map(filter_psc, pieces):
                    list_postcodes.extend(piece)
                prog.update(len(rows))

    click.echo("Adding %d postcodes..." % len(list_postcodes))
    db.session.add_all(list_postcodes)
    click.echo("Committing changes to database...")
    db.session.commit()


if __name__ == "__main__":
    NSPL = os.path.join(ROOT_DIR, "temp/data/nspl.csv")
    with current_app.app_context():
        commit_nspl_data(nspl_file=NSPL)
