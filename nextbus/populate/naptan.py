"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import os
import re
import collections
import dateutil.parser
import click
from flask import current_app

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import capitalise, file_ops, progress_bar, XMLDocument

# TODO: Use INSERT ON CONFLICT for NPTG and NaPTAN entries

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
    "name":             "s:Descriptor/s:CommonName",
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
    """ Collects a list of database entries from XML data and commits them. """
    def __init__(self, xpath):
        self.xpath = xpath
        self.entries = []

    def add(self, list_elements, db_model, args, label=None, parse=None):
        """ Iterates through a list of elements, creating a database model
            object with XPath queries and adding to list. With a parsing
            function, each entry can be filtered out or modified.

            All existing rows are deleted before iterating.

            :param list_elements: List of XML elements to iterate over
            :param db_model: SQLAlchemy database model to create object from
            :param args: Dictionary of args to be passed to database model,
            with values the XPath queries to retrieve values from
            :param label: Label for the progress bar
            :param parse: Function to evaluate each new object, with two
            arguments - list of existing objects (self.entries) and the current
            object being evaluated. Not expected to return anything
        """
        db_model.query.delete()

        with progress_bar(list_elements, label=label) as iter_elements:
            for element in iter_elements:
                obj = db_model(**self.xpath.dict_text(args, element=element))
                if not parse:
                    self.entries.append(obj)
                    continue
                try:
                    parse(self.entries, obj)
                except TypeError as err:
                    if 'positional argument' in str(err):
                        raise TypeError("Filter function must receive two "
                                        "arguments: list of existing objects "
                                        "and the current object.") from err
                    else:
                        raise

    def commit(self):
        """ Commits all entries to database. """
        try:
            db.session.begin()
            click.echo("Adding %d objects to session..." % len(self.entries))
            db.session.add_all(self.entries)
            click.echo("Committing changes to database...")
            db.session.commit()
        except:
            db.session.rollback()
            raise
        finally:
            db.session.close()


def _parse_nptg_places(list_objects, new_obj):
    """ Parses regions, areas and districts. """
    if new_obj.modified is not None:
        new_obj.modified = dateutil.parser.parse(new_obj.modified)
    new_obj.code = new_obj.code.upper()
    list_objects.append(new_obj)


def _parse_localities(list_objects, local):
    """ Parses localities and set district code '310' to None. """
    if local.modified is not None:
        local.modified = dateutil.parser.parse(local.modified)
    local.code = local.code.upper()
    # 310 is used if locality is not within a district
    if local.district_code == '310':
        local.district_code = None
    list_objects.append(local)


def _get_nptg_data(nptg_file, atco_codes=None):
    """ Parses NPTG XML data, getting lists of regions, administrative areas,
        districts and localities that fit specified ATCO code (or all of them
        if atco_codes is None).
    """
    click.echo("Opening NPTG file %r..." % nptg_file)
    nxp = XMLDocument(nptg_file, 'n')

    if atco_codes:
        # Filter by ATCO area - use NPTG data to find correct admin area codes
        click.echo("Checking ATCO areas...")
        admin_areas = []
        invalid_codes = []
        for code in atco_codes:
            area = nxp("//n:AdministrativeArea[n:AtcoAreaCode='%s']" % code)
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


def _remove_districts():
    """ Removes districts without associated localities.
    """
    query_districts = (
        db.session.query(models.District.code)
        .outerjoin(models.District.localities)
        .filter(models.Locality.code.is_(None))
    )
    list_orphaned_districts = [d.code for d in query_districts.all()]
    try:
        db.session.begin()
        click.echo("Deleting orphaned stop areas...")
        models.District.query.filter(
            models.District.code.in_(list_orphaned_districts)
        ).delete(synchronize_session='fetch')
        db.session.commit()
    except:
        db.session.rollback()
        raise
    finally:
        db.session.close()


class _NaPTANStops(object):
    """ Filters NaPTAN stop points and areas by checking duplicates and
        ensuring only stop areas belonging to stop points within specified
        ATCO areas are filtered.
    """
    regex_no_word = re.compile(r"^[^\w]*$")
    indicator_regex = [
        (re.compile(r"(adjacent|adj)", re.I), "adj"),
        (re.compile(r"after", re.I), "aft"),
        (re.compile(r"before", re.I), "bef"),
        (re.compile(r"^(near|nr)$", re.I), "near"),
        (re.compile(r"(opposite|opp)", re.I), "opp"),
        (re.compile(r"^(outside|o/s|os)$", re.I), "o/s"),
        (re.compile(r"^at$", re.I), "at"),
        (re.compile(r"^by$", re.I), "by"),
        (re.compile(r"^(cnr|corner)$", re.I), "cnr"),
        (re.compile(r"(Bay|Gate|Stance|Stand|Stop) ([A-Za-z0-9]+)", re.I), r"\2"),
        (re.compile(r"([ENSW]+)[-\s]?bound", re.I), r">\1"),
        (re.compile(r"->([ENSW]+)", re.I), r">\1"),
        (re.compile(r"(East|North|South|West)[-\s]?bound", re.I),
         lambda m: ">" + m.group(0)[0].upper()),
        (re.compile(r"(\w{6,})", re.I), lambda m: m.group(0)[:4] + '.'),
        (re.compile(r"(\w+.?) (\w+\.?) .*", re.I), r"\1 \2")
    ]

    def __init__(self, list_admin_area_codes=None, list_locality_codes=None):
        self.naptan_codes = set([])
        self.area_codes = set([])
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

    def _stop_exists(self, list_objects, stop_point):
        """ Checks if stop has already been entered and replace with latest
            record. Returns True if stop already exists and is newer, or False
            if this stop is new.
        """
        if stop_point.naptan_code in self.naptan_codes:
            for obj in list_objects:
                if getattr(obj, 'naptan_code', None) == stop_point.naptan_code:
                    duplicate = obj
                    break
            if (stop_point.modified is not None and
                    duplicate.modified >= stop_point.modified):
                return True
            else:
                list_objects.remove(duplicate)
        else:
            self.naptan_codes.add(stop_point.naptan_code)

        return False

    def parse_areas(self, list_objects, area):
        """ Parses stop areas. """
        if area.modified is not None:
            area.modified = dateutil.parser.parse(area.modified)
        # Set all ATCO codes to uppercase
        area.code = area.code.upper()
        # A lot of stop areas have this mistyped stop area type.
        if area.stop_area_type == 'GBPS':
            area.stop_area_type = 'GPBS'
        # '/' is not allowed in NaPTAN strings; was simply removed
        area.name = area.name.replace('  ', ' / ')
        self.area_codes.add(area.code)
        list_objects.append(area)

    def parse_points(self, list_objects, point):
        """ Parses stop points. """
        if point.naptan_code is None:
            # Skip over if stop point does not have a NaPTAN code
            return
        if self.admin_codes:
            if (point.admin_area_code not in self.admin_codes
                    or point.locality_code not in self.locality_codes):
                return

        if point.modified is not None:
            point.modified = dateutil.parser.parse(point.modified)
        # Set all NaPTAN codes to lowercase and all ATCO codes to uppercase
        point.atco_code = point.atco_code.upper()
        point.naptan_code = point.naptan_code.lower()
        # Checks if record already exists
        if self._stop_exists(list_objects, point):
            return

        # Create short indicator for display
        point.short_ind = self._replace_ind(point.indicator)
        # '/' is not allowed in NaPTAN strings; was simply removed
        if point.name is not None:
            point.name = point.name.replace('  ', ' / ')
        # Replace non-word values (eg '---') with None for descriptors
        for attr in ['street', 'crossing', 'landmark']:
            point_desc = getattr(point, attr)
            if point_desc is not None:
                if self.regex_no_word.match(point_desc) or point_desc.lower() == 'none':
                    setattr(point, attr, None)
                elif not any(i.islower() for i in point_desc):
                    # Capitalise descriptors that were in all capitals
                    setattr(point, attr, capitalise(point_desc))
        if point.stop_area_code not in self.area_codes:
            point.stop_area_code = None

        list_objects.append(point)


def _remove_stop_areas():
    """ Remove all stop areas that do not belong within specified admin areas,
        and add locality info based on stops contained within the stop areas.
    """
    # Find all stop areas without any stop points (ie they are outside
    # specified areas)
    query_del = (
        db.session.query(models.StopArea.code)
        .outerjoin(models.StopArea.stop_points)
        .filter(models.StopPoint.atco_code.is_(None))
    )
    list_del = [sa.code for sa in query_del.all()]
    # Find locality codes as modes of stop points within each stop area.
    # Stop areas are repeated if there are multiple modes.
    c_stops = (
        db.session.query(
            models.StopArea.code.label('a_code'),
            models.StopPoint.locality_code.label('l_code'),
            db.func.count(models.StopPoint.atco_code).label('n_stops')
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code, models.StopPoint.locality_code)
    ).subquery()
    m_stops = (
        db.session.query(
            c_stops.c.a_code, c_stops.c.l_code,
            db.func.max(c_stops.c.n_stops).label('max_stops')
        ).group_by(c_stops.c.a_code, c_stops.c.l_code)
    ).subquery()

    query_area_localities = (
        db.session.query(
            c_stops.c.a_code, c_stops.c.l_code
        ).join(m_stops, db.and_(
            c_stops.c.a_code == m_stops.c.a_code,
            c_stops.c.l_code == m_stops.c.l_code,
            c_stops.c.n_stops == m_stops.c.max_stops
        ))
    )

    dict_areas = collections.defaultdict(list)
    update_areas, invalid_areas = [], []
    click.echo("Linking stop areas with localities...")
    for res in query_area_localities.all():
        dict_areas[res[0]].append(res[1])
    for area, local in dict_areas.items():
        if len(local) == 1:
            update_areas.append({'code': area, 'locality_code': local[0]})
        else:
            invalid_areas.append("Stop area %s has multiple localities %s"
                                 % (area, ', '.join(local)))

    try:
        db.session.begin()
        click.echo("Deleting orphaned stop areas...")
        models.StopArea.query.filter(
            models.StopArea.code.in_(list_del)
        ).delete(synchronize_session='fetch')
        click.echo("Adding locality codes to stop areas...")
        db.session.bulk_update_mappings(models.StopArea, update_areas)
        db.session.commit()
    except:
        db.session.rollback()
        raise
    else:
        click.echo('\n'.join(invalid_areas))


def _get_naptan_data(naptan_file, list_area_codes=None):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.
    """
    click.echo("Opening NaPTAN file %r..." % naptan_file)
    sxp = XMLDocument(naptan_file, 's')

    if list_area_codes:
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

    # GBPS is a common typo for GPBS in NapTAN data
    area_types = ' or '.join(".='%s'" % t for t in ['GBPS', 'GCLS', 'GBCS', 'GPBS', 'GTMU'])
    stop_area_path = ("s:StopAreas/s:StopArea[@Status='active']"
                      "[%s(s:StopAreaType[%s])]" % (any_area_query, area_types))
    stop_areas = sxp(stop_area_path)

    return sxp, stop_points, stop_areas


def _get_atco_codes():
    """ Helper function to get list of ATCO codes from config. """
    get_atco_codes = current_app.config.get('ATCO_CODES')
    if get_atco_codes == 'all':
        codes = None
    elif isinstance(get_atco_codes, list):
        # Add ATCO area code 940 for trams
        try:
            codes = [int(i) for i in get_atco_codes]
        except TypeError as err:
            raise TypeError("All ATCO codes must be integers.") from err
        if 940 not in codes:
            codes.append(940)
    else:
        raise ValueError("ATCO codes must be set to either 'all' or a list of "
                         "codes to filter.")

    return codes


def commit_nptg_data(nptg_file=None):
    """ Convert NPTG data (regions admin areas, districts and localities) to
        database objects and commit them to the application database.
    """
    atco_codes = _get_atco_codes()
    if nptg_file is None:
        click.echo("Downloading NPTG.xml from the DfT site...")
        downloaded_files = download_nptg_data()
        nptg_path = downloaded_files[0]
    else:
        nptg_path = nptg_file

    nxp, admin_areas, regions, districts, localities = _get_nptg_data(nptg_path, atco_codes)
    nptg = _DBEntries(nxp)
    nptg.add(regions, models.Region, PATHS_REGION, "Parsing NPTG regions",
             _parse_nptg_places)
    nptg.add(admin_areas, models.AdminArea, PATH_ADMIN_AREA, "Parsing NPTG admin areas",
             _parse_nptg_places)
    nptg.add(districts, models.District, PATHS_DISTRICT, "Parsing NPTG districts",
             _parse_nptg_places)
    nptg.add(localities, models.Locality, PATHS_LOCALITY, "Parsing NPTG localities",
             _parse_localities)
    # Commit changes to database
    nptg.commit()
    # Remove all orphaned districts
    _remove_districts()

    click.echo("NPTG population done.")


def commit_naptan_data(naptan_file=None):
    """ Convert NaPTAN data (stop points and areas) to database objects and
        commit them to the application database.
    """
    atco_codes = _get_atco_codes()
    if naptan_file is None:
        click.echo("Downloading Naptan.xml from the DfT site...")
        downloaded_files = download_naptan_data(atco_codes)
        naptan_path = downloaded_files[0]
    else:
        naptan_path = naptan_file

    query_areas = db.session.query(models.AdminArea.code).all()
    query_local = db.session.query(models.Locality.code).all()
    if not (query_areas and query_local):
        raise ValueError("NPTG tables are not populated; stop point data "
                         "cannot be added without the required locality data."
                         "Run the commit NPTG data function first.")

    if atco_codes:
        area_codes = set(x[0] for x in query_areas)
        local_codes = set(x[0] for x in query_local)
    else:
        area_codes = None
        local_codes = None

    sxp, stop_points, stop_areas = _get_naptan_data(naptan_path, area_codes)
    eval_stops = _NaPTANStops(area_codes, local_codes)
    naptan = _DBEntries(sxp)
    naptan.add(stop_areas, models.StopArea, PATHS_STOP_AREA, "Parsing NaPTAN stop areas",
               eval_stops.parse_areas)
    naptan.add(stop_points, models.StopPoint, PATHS_STOP_POINT, "Parsing NaPTAN stop points",
               eval_stops.parse_points)
    # Commit changes to database
    naptan.commit()
    # Remove all orphaned stop areas and add localities to other stop areas
    _remove_stop_areas()

    click.echo("NaPTAN population done.")


if __name__ == "__main__":
    NAPTAN = os.path.join(ROOT_DIR, "temp/Naptan.xml")
    NPTG = os.path.join(ROOT_DIR, "temp/NPTG.xml")
    with current_app.app_context():
        commit_nptg_data(nptg_file=NPTG)
        commit_naptan_data(naptan_file=NAPTAN)
