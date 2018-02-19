"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import collections
import functools
import operator
import os

import lxml.etree as et
import click
import pyparsing as pp

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import (DBEntries, file_ops, get_atco_codes, NXB_EXT_URI,
                              XSLTExtFunctions)


NAPTAN_URL = r"http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx"
NAPTAN_XSLT = r"nextbus/populate/naptan.xslt"
NAPTAN_XML = r"temp/naptan_data.xml"
IND_MAX_CHARS = 5
IND_MAX_WORDS = 2


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


def _create_ind_parser():
    """ Creates the parser for shortening indicator text for stop points. """

    def kw_one_of(*words, replace=None):
        """ Creates an expression of multiple caseless keywords with bitwise
            OR operators.

            If `replace` is specified, a new parse action replacing matched
            keywords with `repl` is added.
        """
        if not words:
            raise TypeError("Arguments must include at least one word.")
        expr = functools.reduce(
            operator.or_, map(pp.CaselessKeyword, words)
        )
        if replace is not None:
            expr = expr.setParseAction(pp.replaceWith(replace))

        return expr

    def action_upper(tokens):
        """ Uppercase the matched substring. """
        return tokens[0].upper()

    def action_abbrv(tokens):
        """ Abbreviates a number of words. """
        return "".join(w[0].upper() for w in tokens)

    def action_arrow(tokens):
        """ Adds arrow to matched substring. """
        return ">" + tokens[0].upper()

    def action_truncate(tokens):
        """ Truncate words to make them fit within indicators. """
        word = tokens[0]
        if len(word) > IND_MAX_CHARS:
            return word[:IND_MAX_CHARS - 1] + "."

    # indicator keywords, eg adjacent or opposite, should be lowercase
    sub_keywords = functools.reduce(operator.or_, [
        kw_one_of("adj", "adjacent", replace="adj"),
        kw_one_of("aft", "after", "beyond", replace="aft"),
        kw_one_of("bef", "before", "behind", replace="bef"),
        kw_one_of("beside", replace="by"),
        kw_one_of("cnr", "corner", replace="cnr"),
        kw_one_of("from", replace="from"),
        kw_one_of("inside", replace="in"),
        kw_one_of("n/r", "near", replace="near"),
        kw_one_of("opp", "opposite", replace="opp"),
        kw_one_of("o/s", "outside", replace="o/s"),
        kw_one_of("towards", replace="to")
    ])
    # First word only; 2-letter words can be confused for valid stop indicators
    # (eg Stop OS or Stop BY)
    first_keywords = functools.reduce(operator.or_, [
        kw_one_of("at", replace="at"),
        kw_one_of("by", replace="by"),
        kw_one_of("in", replace="in"),
        kw_one_of("nr", replace="near"),
        kw_one_of("os", replace="o/s"),
        kw_one_of("to", replace="to")
    ])
    # Exclude common words, eg 'Stop' or 'Bay'. 
    excluded_words = kw_one_of(
        "and", "bay", "gate", "no.", "platform", "stance", "stances", "stand",
        "stop", "the", "to"
    ).suppress()
    # Also exclude any punctuation on their own
    excluded_punct = pp.Word(
        "".join(c for c in pp.printables if c not in pp.alphanums)
    ).suppress()

    # Define directions
    initials = pp.Word("ENSWensw").setParseAction(action_upper)
    directions = pp.oneOf("east north south west", caseless=True)
    # Convert '->NW', '>NW', etc
    dir_arrow = (pp.Optional("-").suppress() + pp.Literal(">").suppress()
                 + initials).setParseAction(action_arrow)
    # or 'nw-bound', 'north west bound', etc to '>NW'
    dir_bound = (
        (pp.OneOrMore(directions).setParseAction(action_abbrv) | initials)
        .setParseAction(action_arrow)
        + pp.Optional("-").suppress() + pp.CaselessLiteral("bound").suppress()
    )
    # All other words should be uppercase and truncated if too long; can
    # include punctuation as well, eg 'A&E'
    other_words = (
        pp.Combine(pp.Word(pp.alphanums) + pp.Optional(pp.Word(pp.printables)))
        .addParseAction(action_upper)
        .addParseAction(action_truncate)
    )
    # Merge all above expressions
    keywords = functools.reduce(operator.or_, [
        sub_keywords, dir_arrow, dir_bound, excluded_words, excluded_punct
    ])
    first_word = first_keywords | keywords
    # Final expression
    expr = pp.Optional(first_word) + pp.ZeroOrMore(keywords | other_words)

    @functools.lru_cache(maxsize=256)
    def parse_indicator(ind_text):
        """ Uses the parser to return a shorter, abbreviated indicator text
            with at most two words. Uses LRU cache to store previous results.
        """
        result = expr.parseString(ind_text)
        new_ind = " ".join(result[:IND_MAX_WORDS])
    
        return new_ind

    return parse_indicator

class _NaPTANStops(object):
    """ Filters NaPTAN stop points and areas by ensuring only stop areas 
        belonging to stop points within specified ATCO areas are filtered.
    """
    def __init__(self, list_locality_codes=None):
        self.area_codes = set([])
        self.locality_codes = list_locality_codes
        self.indicators = {}
        self.ind_parser = _create_ind_parser()

    def parse_areas(self, list_objects, area):
        """ Parses stop areas. """
        self.area_codes.add(area['code'])
        list_objects.append(area)

    def parse_points(self, list_objects, point):
        """ Parses stop points. """
        # Tram stops use the national admin area code for trams; need to use
        # locality code to determine whether stop is within specified area
        if self.locality_codes:
            if point['locality_ref'] not in self.locality_codes:
                return

        # Create short indicator for display
        if point['indicator'] is not None:
            point['short_ind'] = self.ind_parser(point['indicator'])
        else:
            point['indicator'] = ''
            point['short_ind'] = ''

        if point['stop_area_ref'] not in self.area_codes:
            point['stop_area_ref'] = None

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
            models.StopPoint.locality_ref.label('local_code'),
            db.func.count(models.StopPoint.atco_code).label('num_stops')
        ).join(models.StopArea.stop_points)
        .group_by(models.StopArea.code, models.StopPoint.locality_ref)
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
            update_areas.append({'code': area, 'locality_ref': localities[0]})
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


def _merge_naptan_data(naptan_paths):
    """ Merge NaPTAN data from multiple XML files.

        Each NaPTAN XML file has two elements: StopAreas and StopPoints. For
        every additional XML file, all children from these elements are added
        to the elements parsed from the first file, and the resulting element
        tree is returned.
    """
    click.echo("Opening NaPTAN file %r" % naptan_paths[0])
    data = et.parse(naptan_paths[0])

    if len(naptan_paths) > 1:
        # Create XPath queries for stop areas and points
        names = {'n': data.xpath("namespace-uri(.)")}
        def xpath(element, query):
            return element.xpath(query, namespaces=names)

        stop_areas = xpath(data, "n:StopAreas")[0]
        stop_points = xpath(data, "n:StopPoints")[0]
        # If more than one file: open each and use XPath queries to add all
        # points and areas to the first dataset
        for add_file in naptan_paths[1:]:
            click.echo("Adding data from file %r" % add_file)
            new_data = et.parse(add_file)
            for area in xpath(new_data, "n:StopAreas/n:StopArea"):
                stop_areas.append(area)
            for point in xpath(new_data, "n:StopPoints/n:StopPoint"):
                stop_points.append(point)

    return data


def _get_naptan_data(naptan_paths, list_area_codes=None, out_file=None):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.

        :param naptan_paths: List of paths for NaPTAN XML files
        :param list_area_codes: List of administrative area codes
        :param out_file: File path to write transformed data to, relative to
        the project directory. If None the data is returned as a XML
        ElementTree object
    """
    naptan_data = _merge_naptan_data(naptan_paths)
    transform = et.parse(os.path.join(ROOT_DIR, NAPTAN_XSLT))
    ext = et.Extension(XSLTExtFunctions(), None, ns=NXB_EXT_URI)

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

    if out_file:
        new_data.write_output(os.path.join(ROOT_DIR, out_file))
    else:
        return new_data


def commit_naptan_data(naptan_files=None):
    """ Convert NaPTAN data (stop points and areas) to database objects and
        commit them to the application database.
    """
    atco_codes = get_atco_codes()
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
                         "Populate the database with NPTG data first.")

    if atco_codes:
        area_codes = set(a.code for a in query_areas)
        local_codes = set(l.code for l in query_local)
    else:
        area_codes, local_codes = None, None

    _get_naptan_data(naptan_paths, area_codes, out_file=NAPTAN_XML)
    eval_stops = _NaPTANStops(local_codes)
    naptan = DBEntries(NAPTAN_XML)
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
    from flask import current_app

    NAPTAN = os.path.join(ROOT_DIR, "temp/Naptan.xml")
    with current_app.app_context():
        commit_naptan_data(naptan_files=(NAPTAN,))
