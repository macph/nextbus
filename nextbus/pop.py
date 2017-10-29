"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
import csv
import datetime as dt
import json
import os
import lxml.etree as et
import click
import multiprocessing

from definitions import ROOT_DIR
from nextbus import app, db, models

# TODO: Implement some sort of date system; may need to add to table.
# TODO: Multiprocessing module. May need to take out the NaPTAN code checking

PATHS_REGION = {
    "region_code":          "n:RegionCode",
    "region_name":          "n:Name",
    "country":              "n:Country"
}

PATH_ADMIN_AREA = {
    "admin_area_code":      "n:AdministrativeAreaCode",
    "region_code":          "ancestor::n:Region/n:RegionCode",
    "atco_area_code":       "n:AtcoAreaCode",
    "area_name":            "n:Name",
    "area_short_name":      "n:ShortName"
}

PATHS_DISTRICT = {
    "nptg_district_code":   "n:NptgDistrictCode",
    "admin_area_code":      "ancestor::n:AdministrativeArea/n:AdministrativeAreaCode",
    "district_name":        "n:Name"
}

PATHS_LOCALITY = {
    "nptg_locality_code":   "n:NptgLocalityCode",
    "locality_name":        "n:Descriptor/n:LocalityName",
    "admin_area_code":      "n:AdministrativeAreaRef",
    "nptg_district_code":   "n:NptgDistrictRef",
    "easting":              "n:Location/n:Translation/n:Easting",
    "northing":             "n:Location/n:Translation/n:Northing",
    "longitude":            "n:Location/n:Translation/n:Longitude",
    "latitude":             "n:Location/n:Translation/n:Latitude"
}

PATHS_STOP_POINT = {
    "atco_code":            "s:AtcoCode",
    "naptan_code":          "s:NaptanCode",
    "desc_common":          "s:Descriptor/s:CommonName",
    "desc_short":           "s:Descriptor/s:ShortCommonName",
    "desc_landmark":        "s:Descriptor/s:Landmark",
    "desc_street":          "s:Descriptor/s:Street",
    "desc_crossing":        "s:Descriptor/s:Crossing",
    "desc_indicator":       "s:Descriptor/s:Indicator",
    "nptg_locality_code":   "s:Place/s:NptgLocalityRef",
    "suburb":               "s:Place/s:Suburb",
    "town":                 "s:Place/s:Town",
    "easting":              "s:Place/s:Location/s:Translation/s:Easting",
    "northing":             "s:Place/s:Location/s:Translation/s:Northing",
    "longitude":            "s:Place/s:Location/s:Translation/s:Longitude",
    "latitude":             "s:Place/s:Location/s:Translation/s:Latitude",
    "stop_type":            "s:StopClassification/s:StopType",
    "bearing":              ".//s:CompassPoint",
    "stop_area_code":       "s:StopAreas/s:StopAreaRef",
    "admin_area_code":      "s:AdministrativeAreaRef",
    "last_modified":        "@ModificationDateTime"
}

PATHS_STOP_AREA = {
    "stop_area_code":       "s:StopAreaCode",
    "stop_area_name":       "s:Name",
    "admin_area_code":      "s:AdministrativeAreaRef",
    "stop_area_type":       "s:StopAreaType",
    "easting":              "s:Location/s:Translation/s:Easting",
    "northing":             "s:Location/s:Translation/s:Northing",
    "longitude":            "s:Location/s:Translation/s:Longitude",
    "latitude":             "s:Location/s:Translation/s:Latitude"
}


def _progress_bar(iterable, **kwargs):
    """ Returns click.progressbar with specific options. """
    return click.progressbar(
        iterable=iterable,
        bar_template="%(label)-32s [%(bar)s] %(info)s",
        show_pos=True,
        width=50,
        **kwargs
    )


class _XPath(object):
    """ Helper class for XPath queries in a dataset, with the assumption that
        all sub elements have the same namespace.
    """
    def __init__(self, element, prefix):
        self.element = element
        self.namespace = {}
        self.namespace[prefix] = self.element.xpath("namespace-uri(.)")

    def __call__(self, path, element=None):
        element = self.element if element is None else element
        return element.xpath(path, namespaces=self.namespace)

    def text(self, path, element=None):
        """ Calls a XPath query and returns the text contained within the first
            element if it is the only matching result. Returns None if the
            there is no matching element, and raise a ValueError if there are
            multiple matching elements.
        """
        nodes = self(path, element)
        if len(nodes) == 1:
            return getattr(nodes[0], 'text', nodes[0])
        elif len(nodes) > 1:
            element = self.element if element is None else element
            raise ValueError("Multiple elements matching XPath query %r for "
                             "element %r." % (path, element))
        else:
            raise ValueError("No elements match XPath query %r for element "
                             "%r." % (path, element))

    def iter_text(self, path, elements):
        """ Iterates over a list of elements with the same XPath query,
            returning a list of text values. """
        return [self.text(path, element=node) for node in elements]

    def dict_text(self, dict_paths, element=None):
        """ Returns a dict of text values obtained from processing a dict with
            XPath queries as values for a single element. If a query returns no
            elements, the key is assigned value None.
        """
        result = {}
        for arg, path in dict_paths.items():
            try:
                text = self.text(path, element)
            except ValueError as err:
                if "No elements" in str(err):
                    text = None
                else:
                    raise ValueError from err
            result[arg] = text

        return result


class _DBEntries(object):
    """ Collects a list of database entries from XML data. """
    def __init__(self, xpath):
        self.xpath = xpath
        self.entries = []

    def add(self, list_elements, db_model, args, label=None, func=None):
        """ Iterates through a list of elements, creating a database model
            object with XPath queries and adding to list. With a function,
            each entry can be filtered out or modified.

            Filter functions must have two arguments: list of existing objects
            and the current object being evaluated.
        """
        with _progress_bar(list_elements, label=label) as iter_elements:
            for element in iter_elements:
                obj = db_model(**self.xpath.dict_text(args, element=element))
                if func:
                    try:
                        new_obj = func(self.entries, obj)
                    except TypeError as err:
                        raise TypeError("Filter function must receive two arguments: list of "
                                        "existing objects and the current object.") from err
                    else:
                        if new_obj:
                            self.entries.append(new_obj)
                else:
                    self.entries.append(obj)

    def commit(self):
        """ Commits all entries to database. """
        click.echo("Adding %d objects to session..." % len(self.entries))
        db.session.add_all(self.entries)
        click.echo("Committing changes to database...")
        db.session.commit()


class _NaPTANStops(object):
    """ Filters NaPTAN stop points and areas by checking duplicates and
        ensuring only stop areas belonging to stop points within specified
        ATCO areas are filtered.
    """
    def __init__(self, list_admin_area_codes=None, list_locality_codes=None):
        self.naptan_codes = set([])
        self.area_codes = set([])
        self.admin_codes = list_admin_area_codes
        self.locality_codes = list_locality_codes

    def filter_points(self, list_objects, obj_point):
        """ Filters stop points. """
        try:
            if obj_point.naptan_code is None:
                # Skip over if stop point does not have a NaPTAN code
                return
        except AttributeError as error:
            raise AttributeError("StopPoint objects accepted only.") from error

        if self.admin_codes:
            if (obj_point.admin_area_code not in self.admin_codes
                    or obj_point.nptg_locality_code not in self.locality_codes):
                return
        if obj_point.last_modified is not None:
            obj_point.last_modified = dt.datetime.strptime(obj_point.last_modified,
                                                           "%Y-%m-%dT%H:%M:%S")
        if obj_point.naptan_code in self.naptan_codes:
            # Duplicate found; find it
            for obj in list_objects:
                if getattr(obj, 'naptan_code') == obj_point.naptan_code:
                    obj_duplicate = obj
                    break
            # Check dates; keep the newest
            if obj_duplicate.last_modified > obj_point.last_modified:
                return
            else:
                list_objects.remove(obj_duplicate)
        else:
            self.naptan_codes.add(obj_point.naptan_code)
        # '/' was not allowed in the NaPTAN database; it was simply removed
        if obj_point.desc_common is not None:
            obj_point.desc_common = obj_point.desc_common.replace('  ', ' / ')
        if obj_point.desc_short is not None:
            obj_point.desc_short = obj_point.desc_short.replace('  ', ' / ')
        # Filter stop areas depending on stop points found
        self.area_codes.add(obj_point.stop_area_code)

        return obj_point

    def filter_areas(self, list_objects, obj_area):
        """ Filters stop areas. """
        try:
            if not self.admin_codes or obj_area.stop_area_code in self.area_codes:
                return obj_area
        except AttributeError as error:
            raise AttributeError("StopArea objects accepted only.") from error


def _get_nptg_data(nptg_file, atco_codes=None):
    """ Parses NPTG XML data, getting lists of regions, administrative areas,
        districts and localities that fit specified ATCO code (or all of them
        if atco_codes is None).
    """
    click.echo("Opening NPTG file %r..." % nptg_file)
    nptg_data = et.parse(nptg_file)
    nxp = _XPath(nptg_data, 'n')

    if atco_codes:
        # Filter by ATCO area - use NPTG data to find correct admin area codes
        click.echo("Checking ATCO areas...")
        admin_areas = []
        invalid_codes = []
        for code in atco_codes:
            area = nxp("//n:AdministrativeArea[n:AtcoAreaCode='%d']" % code)
            if area:
                admin_areas.append(area[0])
            else:
                invalid_codes.append(code)
        if invalid_codes:
            raise click.BadOptionUsage(
                "The following ATCO codes cannot be found: %s."
                % ", ".join(repr(i) for i in invalid_codes)
            )

        # Find all matching admin area elements first
        area_codes = nxp.iter_text("n:AdministrativeAreaCode", admin_areas)
        area_query = ' or '.join(".='%s'" % a for a in area_codes)
        regions = nxp("n:Regions/n:Region[.//n:AdministrativeAreaCode[%s]]" % area_query)
        districts = nxp("n:Regions//n:AdministrativeArea[n:AdministrativeAreaCode[%s]]"
                        "//n:NptgDistrict" % area_query)
        localities = nxp("n:NptgLocalities/n:NptgLocality[n:AdministrativeAreaRef[%s]]"
                         % area_query)
    else:
        # Just find all regions, admin areas and localities
        admin_areas = nxp("n:Regions//n:AdministrativeArea")
        regions = nxp("n:Regions/n:Region")
        districts = nxp("n:Regions//n:NptgDistrict")
        localities = nxp("n:NptgLocalities/n:NptgLocality")

    return nxp, admin_areas, regions, districts, localities


def _get_naptan_data(naptan_file, list_area_codes=None):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.
    """
    click.echo("Opening NaPTAN file %r..." % naptan_file)
    naptan_data = et.parse(naptan_file)
    sxp = _XPath(naptan_data, 's')

    if list_area_codes:
        # add 147 for trams/metro
        list_aa_codes = list_area_codes + ['147']
        aa_query = ' or '.join(".='%s'" % a for a in list_aa_codes)
        any_area_query = "(s:AdministrativeAreaRef[%s])" % aa_query + ' and '
    else:
        any_area_query = ''

    click.echo("Getting list of stop points and stop areas...")
    # Put together XPath queries - filter to active stops and of certain types
    stop_types = ' or '.join(".='%s'" % t for t in ['BCT', 'BCS', 'PLT'])
    stop_point_path = ("s:StopPoints/s:StopPoint[@Status='active']"
                       "[%s(s:StopClassification/s:StopType[%s])]" % (any_area_query, stop_types))
    stop_points = sxp(stop_point_path)

    area_types = ' or '.join(".='%s'" % t for t in ['GBPS', 'GCLS', 'GBCS', 'GTMU'])
    stop_area_path = ("s:StopAreas/s:StopArea[@Status='active']"
                      "[%s(s:StopAreaType[%s])]" % (any_area_query, area_types))
    stop_areas = sxp(stop_area_path)

    return sxp, stop_points, stop_areas


def commit_naptan_data(nptg_file, naptan_file, atco_codes=None):
    """ Convert NPTG data (regions admin areas, districts and localities) and
        NaPTAN data (stop points and areas) to database objects and commit them
        to the application database.
    """
    nxp, admin_areas, regions, districts, localities = _get_nptg_data(nptg_file, atco_codes)
    nptg = _DBEntries(nxp)
    nptg.add(regions, models.Region, PATHS_REGION, "Parsing NPTG regions")
    nptg.add(admin_areas, models.AdminArea, PATH_ADMIN_AREA, "Parsing NPTG admin areas")
    nptg.add(districts, models.District, PATHS_DISTRICT, "Parsing NPTG districts")
    nptg.add(localities, models.Locality, PATHS_LOCALITY, "Parsing NPTG localities")
    nptg.commit()

    if atco_codes:
        area_codes = set(nxp.iter_text("n:AdministrativeAreaCode", admin_areas))
        locality_codes = set(nxp.iter_text("n:NptgLocalityCode", localities))
    else:
        area_codes = None
        locality_codes = None

    sxp, stop_points, stop_areas = _get_naptan_data(naptan_file, area_codes)
    eval_stops = _NaPTANStops(area_codes, locality_codes)
    naptan = _DBEntries(sxp)
    naptan.add(stop_points, models.StopPoint, PATHS_STOP_POINT, "Parsing NaPTAN stop points",
               eval_stops.filter_points)
    naptan.add(stop_areas, models.StopArea, PATHS_STOP_AREA, "Parsing NaPTAN stop areas",
               eval_stops.filter_areas)
    naptan.commit()


def commit_nspl_data(atco_codes=None, nspl_file=None):
    """ Converts NSPL data (postcodes) to database objects and commit them
        to the working database.
    """
    la_file = os.path.join(ROOT_DIR, "nextbus/local_authorities.json")
    with open(la_file, 'r') as jf:
        data = json.load(jf)

    if atco_codes:
        dict_la = {local_auth.pop("la_code"): local_auth for local_auth in data
                   if local_auth["admin_area_code"] in atco_codes}
    else:
        dict_la = {local_auth.pop("la_code"): local_auth for local_auth in data}

    click.echo("Opening file %r..." % nspl_file)
    cf = open(nspl_file, 'r')
    # Find number of rows in CSV file
    len_lines = sum(1 for r in csv.reader(cf)) - 1
    # reset read location
    cf.seek(0)

    list_postcodes = []
    with _progress_bar(csv.DictReader(cf), label="Parsing postcode data",
                       length=len_lines) as iter_postcodes:
        for row in iter_postcodes:
            if atco_codes and row["Local Authority Code"] not in dict_la:
                # Filter by ATCO area code if it applies
                continue
            if row["Country Code"] not in ['E92000001', 'S92000003', 'W92000004']:
                # Don't need NI, IoM or the Channel Islands
                continue
            if row["Positional Quality"] in [8, 9]:
                # Low accuracy; just skip row
                continue
            local_authority = dict_la[row["Local Authority Code"]]
            postcode = models.Postcode(
                postcode=row["Postcode 3"],
                postcode_2=''.join(row["Postcode 3"].split()),
                local_authority_code=row["Local Authority Code"],
                admin_area_code=local_authority["admin_area_code"],
                district_code=local_authority["nptg_district_code"],
                easting=row["Easting"],
                northing=row["Northing"],
                longitude=row["Longitude"],
                latitude=row["Latitude"]
            )
            list_postcodes.append(postcode)
    cf.close()

    click.echo("Adding %d postcodes..." % len(list_postcodes))
    db.session.add_all(list_postcodes)
    click.echo("Committing changes to database...")
    db.session.commit()


if __name__ == "__main__":
    NAPTAN = os.path.join(ROOT_DIR, "temp/data/Naptan.xml")
    NPTG = os.path.join(ROOT_DIR, "temp/data/NPTG.xml")
    NSPL = os.path.join(ROOT_DIR, "temp/data/nspl.csv")
    with app.app_context():
        commit_naptan_data(nptg_file=NPTG, naptan_file=NAPTAN)
        commit_nspl_data(nspl_file=NSPL)
