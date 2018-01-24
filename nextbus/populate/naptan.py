"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import os
import re
import collections
import dateutil.parser
import lxml.etree as et
import click
from flask import current_app

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, nxb_xml_ext, progress_bar


NPTG_URL = r'http://naptan.app.dft.gov.uk/datarequest/nptg.ashx'
NAPTAN_URL = r'http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx'
NPTG_XSLT = r"nextbus/populate/nptg.xslt"
NPTG_XML = r"temp/nptg_data.xml"
NAPTAN_XSLT = r"nextbus/populate/naptan.xslt"
NAPTAN_XML = r"temp/naptan_data.xml"


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

    new = file_ops.download_zip(NAPTAN_URL, files, directory=temp_path,
                                params=params)

    return new


def download_nptg_data():
    """ Downloads NPTG data from the DfT. Comes in a zipped file so the NPTG
        XML file is extracted first.
    """
    params = {'format': 'xml'}
    temp_path = os.path.join(ROOT_DIR, 'temp')
    files = ['NPTG.xml']

    new = file_ops.download_zip(NPTG_URL, files, directory=temp_path,
                                params=params)

    return new


class _DBEntries(object):
    """ Collects a list of database entries from XML data and commits them. """
    def __init__(self, xml_data):
        self.data = et.parse(xml_data)
        self.entries = {}

    @staticmethod
    def _element_to_dict(element):
        """ Helper function to create a dictionary from a XML ElementTree
            element. Each of the subelements must match a column in the model.
        """
        data = {i.tag: i.text for i in element}
        if data.get('modified'):
            # Convert to a datetime object if modified date exists and not None
            data['modified'] = dateutil.parser.parse(data['modified'])

        return data

    def add(self, xpath_query, model, label=None, parse=None):
        """ Iterates through a list of elements, creating a list of dicts. With
            a parsing function, each entry can be filtered out or modified.

            All existing rows are deleted before iterating.

            :param xpath_query: XPath query to retrieve list of elements
            :param model: Database model
            :param label: Label for the progress bar
            :param parse: Function to evaluate each new object, with two
            arguments - list of existing objects and the current object being
            evaluated. Not expected to return anything
        """
        model_name = model.__name__
        model.query.delete()

        list_elements = self.data.xpath(xpath_query)
        self.entries[model_name] = []
        with progress_bar(list_elements, label=label) as iter_elements:
            for element in iter_elements:
                data = self._element_to_dict(element)
                if not parse:
                    self.entries[model_name].append(data)
                    continue
                try:
                    parse(self.entries[model_name], data)
                except TypeError as err:
                    if 'positional argument' in str(err):
                        raise TypeError("Filter function must receive two "
                                        "arguments: list of existing objects "
                                        "and the current object.") from err
                    else:
                        raise

    def commit(self):
        """ Commits all entries to database. """
        if not self.entries:
            raise ValueError("No data have been added yet.")
        try:
            for model, data in self.entries.items():
                click.echo("Adding %d %s objects to session"
                           % (len(data), model))
                db.session.bulk_insert_mappings(getattr(models, model), data)
            click.echo("Committing changes to database")
            db.session.commit()
        except:
            db.session.rollback()
            raise
        finally:
            db.session.close()


def _get_nptg_data(nptg_file, atco_codes=None):
    """ Parses NPTG XML data, getting lists of regions, administrative areas,
        districts and localities that fit specified ATCO code (or all of them
        if atco_codes is None). Returns path of file with new XML data.
    """
    click.echo("Opening NPTG file %r" % nptg_file)
    data = et.parse(nptg_file)
    names = {'n': data.xpath("namespace-uri(.)")}

    if atco_codes:
        # Filter by ATCO area - use NPTG data to find correct admin area codes
        click.echo("Checking ATCO areas")
        admin_areas = []
        invalid_codes = []
        for code in atco_codes:
            area = data.xpath("//n:AdministrativeArea[n:AtcoAreaCode='%s']"
                              % code, namespaces=names)
            if area:
                admin_areas.append(area[0])
            else:
                invalid_codes.append(code)
        if invalid_codes:
            raise click.BadOptionUsage(
                "The following ATCO codes cannot be found: %s."
                % ", ".join(repr(i) for i in invalid_codes)
            )
        area_codes = []
        for area in admin_areas:
            code = area.xpath("n:AdministrativeAreaCode", namespaces=names)
            area_codes.append(code)
        area_query = ' or '.join(".='%s'" % a for a in area_codes)

        region_ref = ".//n:AdministrativeAreaCode[%s]" % area_query
        area_ref = "n:AdministrativeAreaCode[%s]" % area_query
        local_ref = "n:AdministrativeAreaRef[%s]" % area_query
    else:
        # Just find all regions, admin areas and localities
        region_ref, area_ref, local_ref = "true()", "true()", "true()"

    xslt_transform = et.parse(os.path.join(ROOT_DIR, NPTG_XSLT))
    click.echo("Applying XSLT tranform to NPTG data")
    new_data = data.xslt(xslt_transform, extensions=nxb_xml_ext, aa=area_ref,
                         la=local_ref, ra=region_ref)
    new_data.write_output(os.path.join(ROOT_DIR, NPTG_XML))

    return NPTG_XML


def _remove_districts():
    """ Removes districts without associated localities. """
    query_districts = (
        db.session.query(models.District.code)
        .outerjoin(models.District.localities)
        .filter(models.Locality.code.is_(None))
    )
    list_orphaned_districts = [d.code for d in query_districts.all()]
    try:
        click.echo("Deleting orphaned stop areas")
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
        self.indicators = {}

    def _replace_ind(self, ind_text):
        """ Shortens indicator text to fit inside sign. """
        if ind_text is not None and ind_text not in self.indicators:
            # Calculate new short indicator
            short_indicator = ind_text.upper()
            for regex, repl in self.indicator_regex:
                short_indicator = regex.sub(repl, short_indicator)
            # Add new short indicator to list
            self.indicators[ind_text] = short_indicator
        elif ind_text is not None:
            # short indicator text already in list; use it
            short_indicator = self.indicators.get(ind_text)
        else:
            short_indicator = None

        return short_indicator

    def _stop_exists(self, list_objects, stop_point):
        """ Checks if stop has already been entered and replace with latest
            record. Returns True if stop already exists and is newer, or False
            if this stop is new.
        """
        if stop_point['naptan_code'] in self.naptan_codes:
            for obj in list_objects:
                if obj.get('naptan_code') == stop_point['naptan_code']:
                    duplicate = obj
                    break
            if (stop_point['modified'] is not None and
                    duplicate['modified'] >= stop_point['modified']):
                return True
            else:
                list_objects.remove(duplicate)
        else:
            self.naptan_codes.add(stop_point['naptan_code'])

        return False

    def parse_areas(self, list_objects, area):
        """ Parses stop areas. """
        self.area_codes.add(area['code'])
        list_objects.append(area)

    def parse_points(self, list_objects, point):
        """ Parses stop points. """
        if self.admin_codes:
            if (point['admin_area_code'] not in self.admin_codes
                    or point['locality_code'] not in self.locality_codes):
                return
        # Checks if record already exists
        if self._stop_exists(list_objects, point):
            return

        # Create short indicator for display
        point['short_ind'] = self._replace_ind(point['indicator'])
        if point['stop_area_code'] not in self.area_codes:
            point['stop_area_code'] = None

        list_objects.append(point)


def _modify_stop_areas():
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
    click.echo("Linking stop areas with localities")
    for res in query_area_localities.all():
        dict_areas[res[0]].append(res[1])
    for area, local in dict_areas.items():
        if len(local) == 1:
            update_areas.append({'code': area, 'locality_code': local[0]})
        else:
            invalid_areas.append("Stop area %s has multiple localities %s"
                                 % (area, ', '.join(local)))

    try:
        click.echo("Deleting orphaned stop areas")
        models.StopArea.query.filter(
            models.StopArea.code.in_(list_del)
        ).delete(synchronize_session='fetch')
        click.echo("Adding locality codes to stop areas")
        db.session.bulk_update_mappings(models.StopArea, update_areas)
        db.session.commit()
    except:
        db.session.rollback()
        raise
    else:
        click.echo('\n'.join(invalid_areas))
    finally:
        db.session.close()


def _get_naptan_data(naptan_file, list_area_codes=None):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.
    """
    click.echo("Opening NaPTAN file %r" % naptan_file)
    data = et.parse(naptan_file)

    if list_area_codes:
        area_query = ' or '.join(".='%s'" % a for a in list_area_codes)
        area_ref = "n:AdministrativeAreaRef[%s]" % area_query
    else:
        area_ref = "true()"

    xslt_transform = et.parse(os.path.join(ROOT_DIR, NAPTAN_XSLT))
    click.echo("Applying XSLT tranform to NaPTAN data")
    new_data = data.xslt(xslt_transform, extensions=nxb_xml_ext, aa=area_ref)
    new_data.write_output(os.path.join(ROOT_DIR, NAPTAN_XML))

    return NAPTAN_XML


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
        click.echo("Downloading NPTG.xml from the DfT site")
        downloaded_files = download_nptg_data()
        nptg_path = downloaded_files[0]
    else:
        nptg_path = nptg_file

    new_data = _get_nptg_data(nptg_path, atco_codes)
    nptg = _DBEntries(new_data)
    nptg.add("Regions/Region", models.Region, "Converting NPTG region data")
    nptg.add("AdminAreas/AdminArea", models.AdminArea,
             "Converting NPTG admin area data")
    nptg.add("Districts/District", models.District,
             "Converting NPTG district data")
    nptg.add("Localities/Locality", models.Locality,
             "Converting NPTG locality data")
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
        click.echo("Downloading Naptan.xml from the DfT site")
        downloaded_files = download_naptan_data(atco_codes)
        naptan_path = downloaded_files[0]
    else:
        naptan_path = naptan_file

    query_areas = db.session.query(models.AdminArea.code).all()
    query_local = db.session.query(models.Locality.code).all()
    if not query_areas or not query_local:
        raise ValueError("NPTG tables are not populated; stop point data "
                         "cannot be added without the required locality data."
                         "Run the commit NPTG data function first.")

    if atco_codes:
        area_codes = set(x[0] for x in query_areas)
        local_codes = set(x[0] for x in query_local)
    else:
        area_codes, local_codes = None, None

    new_data = _get_naptan_data(naptan_path, area_codes)
    eval_stops = _NaPTANStops(area_codes, local_codes)
    naptan = _DBEntries(new_data)
    naptan.add("StopAreas/StopArea", models.StopArea,
               "Converting stop area data", eval_stops.parse_areas)
    naptan.add("StopPoints/StopPoint", models.StopPoint,
               "Converting stop point data", eval_stops.parse_points)
    # Commit changes to database
    naptan.commit()
    # Remove all orphaned stop areas and add localities to other stop areas
    _modify_stop_areas()

    click.echo("NaPTAN population done.")


if __name__ == "__main__":
    NAPTAN = os.path.join(ROOT_DIR, "temp/Naptan.xml")
    NPTG = os.path.join(ROOT_DIR, "temp/NPTG.xml")
    with current_app.app_context():
        commit_nptg_data(nptg_file=NPTG)
        commit_naptan_data(naptan_file=NAPTAN)
