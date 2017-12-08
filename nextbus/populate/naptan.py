"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import os
import re
import dateutil.parser
import lxml.etree
import click
from flask import current_app

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import capitalise, file_ops, progress_bar, XPath


NPTG_URL = r'http://naptan.app.dft.gov.uk/datarequest/nptg.ashx'
NAPTAN_URL = r'http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx'

PATHS_REGION = {
    "code":             "n:RegionCode",
    "name":             "n:Name",
    "modified":         "@ModificationDateTime"
}

PATH_ADMIN_AREA = {
    "code":             "n:AdministrativeAreaCode",
    "region_code":      "ancestor::n:Region/n:RegionCode",
    "atco_code":        "n:AtcoAreaCode",
    "name":             "n:Name",
    "modified":         "@ModificationDateTime"
}

PATHS_DISTRICT = {
    "code":             "n:NptgDistrictCode",
    "admin_area_code":  "ancestor::n:AdministrativeArea/n:AdministrativeAreaCode",
    "name":             "n:Name",
    "modified":         "@ModificationDateTime"
}

PATHS_LOCALITY = {
    "code":             "n:NptgLocalityCode",
    "name":             "n:Descriptor/n:LocalityName",
    "parent_code":      "n:ParentNptgLocalityRef",
    "admin_area_code":  "n:AdministrativeAreaRef",
    "district_code":    "n:NptgDistrictRef",
    "easting":          "n:Location/n:Translation/n:Easting",
    "northing":         "n:Location/n:Translation/n:Northing",
    "longitude":        "n:Location/n:Translation/n:Longitude",
    "latitude":         "n:Location/n:Translation/n:Latitude",
    "modified":         "@ModificationDateTime"
}

PATHS_STOP_POINT = {
    "atco_code":        "s:AtcoCode",
    "naptan_code":      "s:NaptanCode",
    "common_name":      "s:Descriptor/s:CommonName",
    "short_name":       "s:Descriptor/s:ShortCommonName",
    "landmark":         "s:Descriptor/s:Landmark",
    "street":           "s:Descriptor/s:Street",
    "crossing":         "s:Descriptor/s:Crossing",
    "indicator":        "s:Descriptor/s:Indicator",
    "locality_code":    "s:Place/s:NptgLocalityRef",
    "easting":          "s:Place/s:Location/s:Translation/s:Easting",
    "northing":         "s:Place/s:Location/s:Translation/s:Northing",
    "longitude":        "s:Place/s:Location/s:Translation/s:Longitude",
    "latitude":         "s:Place/s:Location/s:Translation/s:Latitude",
    "stop_type":        "s:StopClassification/s:StopType",
    "bearing":          ".//s:CompassPoint",
    "stop_area_code":   "s:StopAreas/s:StopAreaRef",
    "admin_area_code":  "s:AdministrativeAreaRef",
    "modified":         "@ModificationDateTime"
}

PATHS_STOP_AREA = {
    "code":             "s:StopAreaCode",
    "name":             "s:Name",
    "admin_area_code":  "s:AdministrativeAreaRef",
    "stop_area_type":   "s:StopAreaType",
    "easting":          "s:Location/s:Translation/s:Easting",
    "northing":         "s:Location/s:Translation/s:Northing",
    "longitude":        "s:Location/s:Translation/s:Longitude",
    "latitude":         "s:Location/s:Translation/s:Latitude",
    "modified":         "@ModificationDateTime"
}


def download_naptan_data(atco_codes=None):
    """ Downloads NaPTAN data from the DfT. Comes in a zipped file so the
        NaPTAN XML data are extracted first.

        :param atco_codes: List of ATCO codes used to filter areas. If None,
        all data in Great Britain (outwith IoM, Channel Islands and Northern
        Ireland) are retrieved.
    """
    params = {'format': 'xml'}
    temp_path = os.path.join(ROOT_DIR, 'temp')

    if atco_codes:
        # Add tram/metro options (ATCO area code 940)
        params['LA'] = '|'.join(str(i) for i in atco_codes + [940])
        files = None
    else:
        files = ['Naptan.xml']

    new = file_ops.download_zip(NAPTAN_URL, files, directory=temp_path, params=params)

    return new


def download_nptg_data():
    """ Downloads NPTG data from the DfT. Comes in a zipped file so the NPTG
        XML file is extracted first.
    """
    params = {'format': 'xml'}
    temp_path = os.path.join(ROOT_DIR, 'temp')
    files = ['NPTG.xml']

    new = file_ops.download_zip(NPTG_URL, files, directory=temp_path, params=params)

    return new


class _DBEntries(object):
    """ Collects a list of database entries from XML data. """
    def __init__(self, xpath):
        self.xpath = xpath
        self.entries = []

    def add(self, list_elements, db_model, args, label=None, func=None):
        """ Iterates through a list of elements, creating a database model
            object with XPath queries and adding to list. With a function,
            each entry can be filtered out or modified.

            All existing rows are deleted before iterating.

            Filter functions must have two arguments: list of existing objects
            and the current object being evaluated.
        """
        db_model.query.delete()

        with progress_bar(list_elements, label=label) as iter_elements:
            for element in iter_elements:
                obj = db_model(**self.xpath.dict_text(args, element=element))
                if not func:
                    self.entries.append(obj)
                    continue
                try:
                    func(self.entries, obj)
                except TypeError as err:
                    if 'positional argument' in str(err):
                        raise TypeError("Filter function must receive two "
                                        "arguments: list of existing objects "
                                        "and the current object.") from err
                    else:
                        raise

    def commit(self):
        """ Commits all entries to database. """
        click.echo("Adding %d objects to session..." % len(self.entries))
        db.session.add_all(self.entries)
        click.echo("Committing changes to database...")
        db.session.commit()


class _NPTGPlaces(object):
    """ Helper class for NPTG areas """
    def __init__(self):
        pass

    def __call__(self, list_objects, new_obj):
        if new_obj.modified is not None:
            new_obj.modified = dateutil.parser.parse(new_obj.modified)
        list_objects.append(new_obj)


def _get_nptg_data(nptg_file, atco_codes=None):
    """ Parses NPTG XML data, getting lists of regions, administrative areas,
        districts and localities that fit specified ATCO code (or all of them
        if atco_codes is None).
    """
    click.echo("Opening NPTG file %r..." % nptg_file)
    nptg_data = lxml.etree.parse(nptg_file)
    nxp = XPath(nptg_data, 'n')

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


class _NaPTANStops(object):
    """ Filters NaPTAN stop points and areas by checking duplicates and
        ensuring only stop areas belonging to stop points within specified
        ATCO areas are filtered.
    """
    regex_no_word = re.compile(r"^[^\w]*$")
    indicator_regex = [
        (re.compile(r"(Bay|Gate|Stance|Stand|Stop) ([A-Za-z0-9]+)", re.I), r"\2"),
        (re.compile(r"(adjacent|adj)", re.I), "adj"),
        (re.compile(r"after", re.I), "aft"),
        (re.compile(r"before", re.I), "pre"),
        (re.compile(r"^(near|nr)$", re.I), "near"),
        (re.compile(r"(opposite|opp)", re.I), "opp"),
        (re.compile(r"(outside|o/s)", re.I), "o/s"),
        (re.compile(r"^at$", re.I), "at"),
        (re.compile(r"([ENSW]+)[-\s]?bound", re.I), r">\1"),
        (re.compile(r"->([ENSW]+)", re.I), r">\1"),
        (re.compile(r"(East|North|South|West)[-\s]?bound", re.I),
         lambda m: ">" + m.group(0)[0].upper()),
        (re.compile(r"(\w{6,})", re.I), lambda m: m.group(0)[:4] + '.'),
        (re.compile(r"(\w+.?) (\w+\.?) .*", re.I), r"\1 \2")
    ]

    def __init__(self, list_admin_area_codes=None, list_locality_codes=None):
        self.naptan_codes = set([])
        self.area_codes = {}
        self.admin_codes = list_admin_area_codes
        self.locality_codes = list_locality_codes

    def _replace_ind(self, ind_text):
        """ Shortens indicator text to fit inside sign. """
        if ind_text is not None:
            short_indicator = ind_text.upper()
            for regex, repl in self.indicator_regex:
                short_indicator = regex.sub(repl, short_indicator)
        else:
            short_indicator = None

        return short_indicator

    def filter_points(self, list_objects, point):
        """ Filters stop points. """
        if point.naptan_code is None:
            # Skip over if stop point does not have a NaPTAN code
            return
        if self.admin_codes:
            if (point.admin_area_code not in self.admin_codes
                    or point.locality_code not in self.locality_codes):
                return

        # Create short indicator for display
        point.short_ind = self._replace_ind(point.indicator)
        # '/' is not allowed in NaPTAN strings; was simply removed
        if point.common_name is not None:
            point.common_name = point.common_name.replace('  ', ' / ')
        if point.short_name is not None:
            point.short_name = point.short_name.replace('  ', ' / ')
        # Replace non-word values (eg '---') with None for descriptors
        for desc in ['street', 'crossing', 'landmark']:
            point_desc = getattr(point, desc)
            if point_desc is not None:
                if self.regex_no_word.match(point_desc) or point_desc.lower() == 'none':
                    setattr(point, desc, None)
                elif not any(i.islower() for i in point_desc):
                    # Capitalise descriptors that were in all capitals
                    setattr(point, desc, capitalise(point_desc))

        if point.modified is not None:
            point.modified = dateutil.parser.parse(point.modified)

        if point.naptan_code in self.naptan_codes:
            for obj in list_objects:
                if getattr(obj, 'naptan_code') == point.naptan_code:
                    duplicate = obj
                    break
            if (point.modified is not None and
                    duplicate.modified >= point.modified):
                return
            else:
                list_objects.remove(duplicate)
        else:
            self.naptan_codes.add(point.naptan_code)

        if point.stop_area_code not in self.area_codes:
            self.area_codes[point.stop_area_code] = [point]
        else:
            self.area_codes[point.stop_area_code].append(point)
        list_objects.append(point)

    def filter_areas(self, list_objects, area):
        """ Filters stop areas. """
        if self.admin_codes and area.code not in self.area_codes:
            return
        if area.code in self.area_codes:
            # Find the most common locality among the stops in area
            loc = list(map(lambda p: p.locality_code, self.area_codes[area.code]))
            count_loc = {l: loc.count(l) for l in set(loc)}
            mode = [i for i, j in count_loc.items() if j == max(count_loc.values())]
            if len(mode) == 1:
                area.locality_code = mode[0]
            else:
                click.echo("\nStop area %s / '%s' has multiple possible localities: %s."
                           % (area.code, area.name, ', '.join(mode)))
        if area.modified is not None:
            area.modified = dateutil.parser.parse(area.modified)
        # '/' is not allowed in NaPTAN strings; was simply removed
        area.name = area.name.replace('  ', ' / ')
        list_objects.append(area)


def _get_naptan_data(naptan_file, list_area_codes=None):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.
    """
    click.echo("Opening NaPTAN file %r..." % naptan_file)
    naptan_data = lxml.etree.parse(naptan_file)
    sxp = XPath(naptan_data, 's')

    if list_area_codes:
        # add 147 for trams/metro
        list_area_codes.add('147')
        aa_query = ' or '.join(".='%s'" % a for a in list_area_codes)
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


def commit_naptan_data(nptg_file=None, naptan_file=None):
    """ Convert NPTG data (regions admin areas, districts and localities) and
        NaPTAN data (stop points and areas) to database objects and commit them
        to the application database.
    """
    get_atco_codes = current_app.config.get('ATCO_CODES')
    if get_atco_codes == 'all':
        atco_codes = None
    elif isinstance(get_atco_codes, list):
        atco_codes = get_atco_codes
    else:
        raise ValueError("ATCO codes must be set to either 'all' or a list of "
                         "codes to filter.")

    nptg_dl = nptg_file is None
    naptan_dl = naptan_file is None
    if nptg_dl:
        click.echo("Downloading NPTG.xml from the DfT site...")
        downloaded_files = download_nptg_data()
        nptg_path = downloaded_files[0]
    else:
        nptg_path = nptg_file
    if naptan_dl:
        click.echo("Downloading Naptan.xml from the DfT site...")
        downloaded_files = download_naptan_data(atco_codes)
        naptan_path = downloaded_files[0]
    else:
        naptan_path = naptan_file


    nxp, admin_areas, regions, districts, localities = _get_nptg_data(nptg_path, atco_codes)
    nptg = _DBEntries(nxp)
    nptg.add(regions, models.Region, PATHS_REGION, "Parsing NPTG regions", _NPTGPlaces())
    nptg.add(admin_areas, models.AdminArea, PATH_ADMIN_AREA, "Parsing NPTG admin areas",
             _NPTGPlaces())
    nptg.add(districts, models.District, PATHS_DISTRICT, "Parsing NPTG districts", _NPTGPlaces())
    nptg.add(localities, models.Locality, PATHS_LOCALITY, "Parsing NPTG localities", _NPTGPlaces())

    if atco_codes:
        area_codes = set(nxp.iter_text("n:AdministrativeAreaCode", admin_areas))
        locality_codes = set(nxp.iter_text("n:NptgLocalityCode", localities))
    else:
        area_codes = None
        locality_codes = None

    sxp, stop_points, stop_areas = _get_naptan_data(naptan_path, area_codes)
    eval_stops = _NaPTANStops(area_codes, locality_codes)
    naptan = _DBEntries(sxp)
    naptan.add(stop_points, models.StopPoint, PATHS_STOP_POINT, "Parsing NaPTAN stop points",
               eval_stops.filter_points)
    naptan.add(stop_areas, models.StopArea, PATHS_STOP_AREA, "Parsing NaPTAN stop areas",
               eval_stops.filter_areas)

    # Commit changes to database
    nptg.commit()
    naptan.commit()

    message = "Population done."
    if nptg_dl and naptan_dl:
        message += " The files 'NPTG.xml' and 'Naptan.xml' are saved in the Temp directory."
    elif nptg_dl:
        message += " The file 'NPTG.xml' is saved in the Temp directory."
    elif naptan_dl:
        message += "The file 'Naptan.xml' is saved in the Temp directory."
    click.echo(message)


if __name__ == "__main__":
    NAPTAN = os.path.join(ROOT_DIR, "temp/data/Naptan.xml")
    NPTG = os.path.join(ROOT_DIR, "temp/data/NPTG.xml")
    with current_app.app_context():
        commit_naptan_data(nptg_file=NPTG, naptan_file=NAPTAN)
