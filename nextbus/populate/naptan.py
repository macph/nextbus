"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import os
import re
import functools
import collections
import dateutil.parser
import lxml.etree as et
import click
from flask import current_app
import sqlalchemy.dialects.postgresql as pg_sql

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, progress_bar


NXB_EXT_URI = r"http://nextbus.org/functions"
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


def _element_text(function):
    """ Converts XPath query result to a string by taking the text content from
        the only element in list before passing it to the extension function.
        If the XPath query returned nothing, the wrapped function will return
        None.
    """
    @functools.wraps(function)
    def _function_with_text(instance, context, result, *args, **kwargs):
        if len(result) == 1:
            try:
                text = result[0].text
            except AttributeError:
                text = str(result[0])
            return function(instance, context, text, *args, **kwargs)
        elif len(result) > 1:
            raise ValueError("XPath query returned multiple elements.")
        else:
            return None

    return _function_with_text


def _element_as_dict(element, **modify):
    """ Helper function to create a dictionary from a XML element.

        Each of the subelements must match a column in the model.

        :param element: XML Element object
        :param modify: Modify data with the keys to identify tags/
        columns and the values the functions used to modify these data. Each
        function must accept one argument.
        :returns: A dictionary with keys matching subelement tags in the
        element.
    """
    data = {i.tag: i.text for i in element}
    for key, func in modify.items():
        if key in data:
            data[key] = func(data[key]) if data[key] is not None else None
        else:
            raise ValueError("Key %s does not match with any tag from the "
                             "data." % key)

    return data


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


class _ExtFunctions(object):
    """ Extension for modifying data in NaPTAN/NPTG data. """

    @_element_text
    def replace(self, _, result, original, substitute):
        """ Replace substrings within content. """
        return result.replace(original, substitute)

    @_element_text
    def upper(self, _, result):
        """ Convert all letters in content to uppercase. """
        return result.upper()

    @_element_text
    def lower(self, _, result):
        """ Convert all letters in content to lowercase. """
        return result.lower()

    @_element_text
    def remove_spaces(self, _, result):
        """ Remove all spaces from content. """
        return ''.join(result.strip())

    @_element_text
    def capitalize(self, _, result):
        """ Capitalises every word in a string, include these enclosed within
            brackets and excluding apostrophes.
        """
        list_words = result.lower().split()
        for _w, word in enumerate(list_words):
            for _c, char in enumerate(word):
                if char.isalpha():
                    list_words[_w] = word[:_c] + char.upper() + word[_c+1:]
                    break
        return ' '.join(list_words)


class _DBEntries(object):
    """ Collects a list of database entries from XML data and commits them. """
    def __init__(self, xml_data):
        self.data = et.parse(xml_data)
        self.entries = collections.OrderedDict()
        self.conflicts = {}

    def add(self, xpath_query, model, label=None, parse=None, constraint=None,
            indices=None):
        """ Iterates through a list of elements, creating a list of dicts.

            With a parsing function, each entry can be filtered out or
            modified. Can add constraint or indices to use in PostgreSQL's
            INSERT ON CONFLICT DO UPDATE statements. All existing rows are
            deleted before iterating.

            :param xpath_query: XPath query to retrieve list of elements
            :param model: Database model
            :param label: Label for the progress bar
            :param parse: Function to evaluate each new object, with two
            arguments - list of existing objects and the current object being
            evaluated. Not expected to return anything
            :param constraint: Name of constraint to evaluate in case of a
            ON CONFLICT DO UPDATE statement
            :param indices: Sequence of string or Column objects to assess
            in a ON CONFLICT DO UPDATE statement
        """
        # Find all elements matching query
        list_elements = self.data.xpath(xpath_query)
        # Assuming keys in every entry are equal
        columns = _element_as_dict(list_elements[0]).keys()

        if constraint is not None and indices is not None:
            raise TypeError("The 'constraint' and 'indices' arguments are "
                            "mutually exclusive.")
        elif constraint is not None:
            self.conflicts[model] = {'constraint': constraint,
                                     'columns': columns}
        elif indices is not None:
            self.conflicts[model] = {'indices': indices, 'columns':columns}

        # Create list for model and iterate over all elements
        self.entries[model] = []
        with progress_bar(list_elements, label=label) as iter_elements:
            for element in iter_elements:
                data = _element_as_dict(
                    element, modified=dateutil.parser.parse
                )
                if not parse:
                    self.entries[model].append(data)
                    continue
                try:
                    parse(self.entries[model], data)
                except TypeError as err:
                    if 'positional argument' in str(err):
                        raise TypeError(
                            "Filter function must receive two arguments: list "
                            "of existing objects and the current object."
                        ) from err
                    else:
                        raise

    def _create_insert_statement(self, model):
        """ Creates an insert statement, depending on whether constraints or
            indices were added.

            :param model: Database model
            :returns: Insert statement to be used by the session.execute()
            function. Values are not included as the execute
            function will add them
        """
        table = model.__table__
        if self.conflicts.get(model):
            # Constraint or indices have been specified; make a INSERT ON
            # CONFLICT DO UPDATE statement
            insert = pg_sql.insert(table)
            # Create arguments, add index elements or constraints
            # 'excluded' is a specific property used in ON CONFLICT statements
            # referring to the inserted row conflicting with an existing row
            args = {
                'set_': {c: getattr(insert.excluded, c) for c in
                         self.conflicts[model]['columns']},
                'where': table.c.modified < insert.excluded.modified
            }
            if 'constraint' in self.conflicts[model]:
                args['constraint'] = self.conflicts[model]['constraint']
            else:
                args['index_elements'] = self.conflicts[model]['indices']
            statement = insert.on_conflict_do_update(**args)
        else:
            # Else, a simple INSERT statement
            statement = table.insert()

        return statement

    def commit(self):
        """ Commits all entries to database. """
        if not self.entries:
            raise ValueError("No data have been added yet.")
        try:
            for model, data in self.entries.items():
                click.echo("Adding %d %s objects to session"
                           % (len(data), model.__name__))
                # Delete existing rows
                db.session.execute(model.__table__.delete())
                # Add new rows
                db.session.execute(self._create_insert_statement(model), data)
            click.echo("Committing changes to database")
            db.session.commit()
        except:
            db.session.rollback()
            raise
        finally:
            db.session.close()


def _remove_districts():
    """ Removes districts without associated localities. """
    query_districts = (
        db.session.query(models.District.code)
        .outerjoin(models.District.localities)
        .filter(models.Locality.code.is_(None))
    )
    orphaned_districts = [d.code for d in query_districts.all()]
    try:
        click.echo("Deleting %d orphaned districts" % len(orphaned_districts))
        models.District.query.filter(
            models.District.code.in_(orphaned_districts)
        ).delete(synchronize_session='fetch')
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
    transform = et.parse(os.path.join(ROOT_DIR, NPTG_XSLT))
    ext = et.Extension(_ExtFunctions(), None, ns=NXB_EXT_URI)

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
        area_codes = [area.xpath("n:AdministrativeAreaCode/text()",
                                 namespaces=names)[0]
                      for area in admin_areas]
        area_query = ' or '.join(".='%s'" % code for code in area_codes)

        # Create new conditions to attach to XPath queries for filtering
        # administrative areas; for example, can do
        # 'n:Element[condition1][condition2]' instead of
        # 'n:Element[condition1 and condition2]'.
        area_ref = {
            'regions': "[.//n:AdministrativeAreaCode[%s]]" % area_query,
            'areas': "[n:AdministrativeAreaCode[%s]]" % area_query,
            'districts': "[ancestor::n:AdministrativeArea/"
                         "n:AdministrativeAreaCode[%s]]" % area_query,
            'localities': "[n:AdministrativeAreaRef[%s]]" % area_query
        }

        # Modify the XPath queries to filter by admin area
        xsl_names = {'xsl': transform.xpath('namespace-uri(.)')}
        for k, ref in area_ref.items():
            param = transform.xpath("//xsl:param[@name='%s']" % k,
                                    namespaces=xsl_names)[0]
            param.attrib['select'] += ref

    click.echo("Applying XSLT transform to NPTG data")
    new_data = data.xslt(transform, extensions=ext)
    new_data.write_output(os.path.join(ROOT_DIR, NPTG_XML))

    return NPTG_XML


def commit_nptg_data(nptg_file=None):
    """ Convert NPTG data (regions admin areas, districts and localities) to
        database objects and commit them to the application database.
    """
    atco_codes = _get_atco_codes()
    if nptg_file is None:
        click.echo("Downloading NPTG data")
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
        (re.compile(r"^on$", re.I), "on"),
        (re.compile(r"^(cnr|corner)$", re.I), "cnr"),
        (re.compile(r"(Bay|Gate|Stance|Stand|Stop) ([A-Za-z0-9]+)", re.I), r"\2"),
        (re.compile(r"([ENSW]+)[-\s]?bound", re.I), r">\1"),
        (re.compile(r"->([ENSW]+)", re.I), r">\1"),
        (re.compile(r"(East|North|South|West)[-\s]?bound", re.I),
         lambda m: ">" + m.group(0)[0].upper()),
        (re.compile(r"(\w{6,})", re.I), lambda m: m.group(0)[:4] + '.'),
        (re.compile(r"(\w+.?) (\w+\.?) .*", re.I), r"\1 \2")
    ]

    def __init__(self, list_locality_codes=None):
        self.area_codes = set([])
        self.locality_codes = list_locality_codes
        self.indicators = {}

    def _replace_ind(self, ind_text):
        """ Shortens indicator text to fit inside sign. """
        if ind_text not in self.indicators:
            # Calculate new short indicator
            short_indicator = ind_text.upper()
            for regex, repl in self.indicator_regex:
                short_indicator = regex.sub(repl, short_indicator)
            # Add new short indicator to list
            self.indicators[ind_text] = short_indicator
        else:
            # short indicator text already in list; use it
            short_indicator = self.indicators.get(ind_text)

        return short_indicator

    def parse_areas(self, list_objects, area):
        """ Parses stop areas. """
        self.area_codes.add(area['code'])
        list_objects.append(area)

    def parse_points(self, list_objects, point):
        """ Parses stop points. """
        # Tram stops use the national admin area code for trams; need to use
        # locality code to determine whether stop is within specified area
        if self.locality_codes:
            if point['locality_code'] not in self.locality_codes:
                return

        # Create short indicator for display
        if point['indicator'] is not None:
            point['short_ind'] = self._replace_ind(point['indicator'])
        else:
            point['indicator'] = ''
            point['short_ind'] = ''

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
            models.StopArea.code.label('area_code'),
            models.StopPoint.locality_code.label('local_code'),
            db.func.count(models.StopPoint.atco_code).label('num_stops')
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code, models.StopPoint.locality_code)
    ).subquery()
    m_stops = (
        db.session.query(
            c_stops.c.area_code, c_stops.c.local_code,
            db.func.max(c_stops.c.num_stops).label('max_stops')
        ).group_by(c_stops.c.area_code, c_stops.c.local_code)
    ).subquery()

    query_area_localities = (
        db.session.query(
            c_stops.c.area_code, c_stops.c.local_code
        ).join(m_stops, db.and_(
            c_stops.c.area_code == m_stops.c.area_code,
            c_stops.c.local_code == m_stops.c.local_code,
            c_stops.c.num_stops == m_stops.c.max_stops
        ))
    )

    dict_areas = collections.defaultdict(list)
    update_areas, invalid_areas = [], []
    click.echo("Linking stop areas with localities")
    for row in query_area_localities.all():
        dict_areas[row.area_code].append(row.local_code)
    for area, localities in dict_areas.items():
        if len(localities) == 1:
            update_areas.append({'code': area, 'locality_code': localities[0]})
        else:
            invalid_areas.append("Stop area %s has multiple localities %s"
                                 % (area, ', '.join(localities)))

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



def _get_naptan_data(naptan_paths, list_area_codes=None):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.
    """
    click.echo("Opening NaPTAN file %r" % naptan_paths[0])
    naptan_data = et.parse(naptan_paths[0])

    if len(naptan_paths) > 1:
        # Create XPath queries for stop areas and points
        _n = {'n': naptan_data.xpath("namespace-uri(.)")}
        stop_areas = naptan_data.xpath("n:StopAreas", namespaces=_n)[0]
        stop_points = naptan_data.xpath("n:StopPoints", namespaces=_n)[0]
        # If more than one file: open each and use XPath queries to add all
        # points and areas to the first dataset
        for _file in naptan_paths[1:]:
            click.echo("Adding data from file %r" % _file)
            data = et.parse(_file)
            for area in data.xpath("n:StopAreas/n:StopArea", namespaces=_n):
                stop_areas.append(area)
            for point in data.xpath("n:StopPoints/n:StopPoint", namespaces=_n):
                stop_points.append(point)

    transform = et.parse(os.path.join(ROOT_DIR, NAPTAN_XSLT))
    ext = et.Extension(_ExtFunctions(), None, ns=NXB_EXT_URI)

    if list_area_codes:
        area_query = ' or '.join(".='%s'" % a for a in list_area_codes)
        area_ref = "[n:AdministrativeAreaRef[%s]]" % area_query

        # Modify the XPath queries to filter by admin area
        xsl_names = {'xsl': transform.xpath("namespace-uri(.)")}
        for ref in ['stops', 'areas']:
            param = transform.xpath("//xsl:param[@name='%s']" % ref,
                                    namespaces=xsl_names)[0]
            param.attrib['select'] += area_ref

    click.echo("Applying XSLT transform to NaPTAN data")
    new_data = naptan_data.xslt(transform, extensions=ext)
    new_data.write_output(os.path.join(ROOT_DIR, NAPTAN_XML))

    return NAPTAN_XML


def commit_naptan_data(naptan_files=None):
    """ Convert NaPTAN data (stop points and areas) to database objects and
        commit them to the application database.
    """
    atco_codes = _get_atco_codes()
    if not naptan_files:
        click.echo("Downloading NaPTAN data")
        naptan_paths = download_naptan_data(atco_codes)
    else:
        naptan_paths = list(naptan_files)

    query_areas = db.session.query(models.AdminArea.code).all()
    query_local = db.session.query(models.Locality.code).all()
    if not query_areas or not query_local:
        raise ValueError("NPTG tables are not populated; stop point data "
                         "cannot be added without the required locality data."
                         "Run the commit NPTG data function first.")

    if atco_codes:
        area_codes = set(a.code for a in query_areas)
        local_codes = set(l.code for l in query_local)
    else:
        area_codes, local_codes = None, None

    new_data = _get_naptan_data(naptan_paths, area_codes)
    eval_stops = _NaPTANStops(local_codes)
    naptan = _DBEntries(new_data)
    naptan.add("StopAreas/StopArea", models.StopArea,
               "Converting stop area data", eval_stops.parse_areas)
    naptan.add("StopPoints/StopPoint", models.StopPoint,
               "Converting stop point data", eval_stops.parse_points,
               indices=('naptan_code',))
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
        commit_naptan_data(naptan_files=(NAPTAN,))
