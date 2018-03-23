"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import collections
import functools
import operator
import os

import lxml.etree as et
import pyparsing as pp

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import (DBEntries, database_session, file_ops,
                              get_atco_codes, logger, merge_xml, NXB_EXT_URI,
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
    params = {"format": "xml"}
    if atco_codes:
        params["LA"] = "|".join(str(i) for i in atco_codes)

    new = file_ops.download(NAPTAN_URL, directory="temp", params=params)

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
        self.area_codes.add(area["code"])
        list_objects.append(area)

    def parse_points(self, list_objects, point):
        """ Parses stop points. """
        # Tram stops use the national admin area code for trams; need to use
        # locality code to determine whether stop is within specified area
        if self.locality_codes:
            if point["locality_ref"] not in self.locality_codes:
                return

        # Create short indicator for display
        if point["indicator"] is not None:
            point["short_ind"] = self.ind_parser(point["indicator"])
        else:
            point["indicator"] = ""
            point["short_ind"] = ""

        if point["stop_area_ref"] not in self.area_codes:
            point["stop_area_ref"] = None

        list_objects.append(point)


def _remove_stop_areas():
    """ Remove all stop areas without associated stop points. """
    query_stop_area_del = (
        db.session.query(models.StopArea.code)
        .outerjoin(models.StopArea.stop_points)
        .filter(models.StopPoint.atco_code.is_(None))
    ).subquery()

    with database_session():
        logger.info("Deleting orphaned stop areas")
        models.StopArea.query.filter(
            models.StopArea.code.in_(query_stop_area_del)
        ).delete(synchronize_session="fetch")


def _find_stop_area_mode(query_result, ref):
    """ Helper function to find the mode of references for each stop area.

        The query results must have 3 columns: primary key, foreign key
        reference and number of stop points within each area matching that
        reference, in that order.

        :param ref: Name of the reference column.
        :returns: Two lists; one to be to be used with ``bulk_update_mappings``
        and the other strings for invalid areas.
    """
    # Group by stop area and reference
    stop_areas = collections.defaultdict(dict)
    for row in query_result:
        stop_areas[row[0]][row[1]] = row[2]

    # Check each area and find mode matching reference
    update_areas = []
    invalid_areas = {}
    for sa, count in stop_areas.items():
        max_count = [k for k, v in count.items() if v == max(count.values())]
        if len(max_count) == 1:
            update_areas.append({"code": sa, ref: max_count[0]})
        else:
            invalid_areas[sa] = max_count

    return update_areas, invalid_areas


def _find_locality_min_distance(ambiguous_areas):
    """ Helper function to find the minimum distance between stop areas and
        localities for these with ambiguous localities.
    """
    distance = db.func.sqrt(
        db.func.power(models.StopArea.easting - models.Locality.easting, 2) +
        db.func.power(models.StopArea.northing - models.Locality.northing, 2)
    )
    # Do another query over list of areas to find distance
    query_dist = (
        db.session.query(
            models.StopArea.code.label("code"),
            models.Locality.code.label("locality"),
            distance.label("distance")
        ).select_from(models.StopPoint)
        .distinct(models.StopArea.code, models.Locality.code)
        .join(models.Locality,
              models.Locality.code == models.StopPoint.locality_ref)
        .join(models.StopArea,
              models.StopArea.code == models.StopPoint.stop_area_ref)
        .filter(models.StopPoint.stop_area_ref.in_(ambiguous_areas))
    )

    # Group by stop area and locality reference
    stop_areas = collections.defaultdict(dict)
    for row in query_dist.all():
        stop_areas[row.code][row.locality] = row.distance
    # Check each area and find the minimum distance
    update_areas = []
    for sa, local in stop_areas.items():
        min_dist = min(local.values())
        local_min = [k for k, v in local.items() if v == min_dist]

        # Check if associated localities are far away - may be wrong locality
        for k, dist in local.items():
            if dist > 2 * min_dist and dist > 1000:
                logger.warning("Area %s: %.0f m away from %s" % (sa, dist, k))

        # Else, check if only one locality matches min distance and set it
        if len(local_min) == 1:
            logger.debug("Area %s set to locality %s, dist %.0f m" %
                         (sa, local_min[0], min_dist))
            update_areas.append({"code": sa, "locality_ref": local_min[0]})
        else:
            logger.warning("Area %s: ambiguous localities %s" % (sa, min_dist))

    return update_areas


def _set_stop_area_locality():
    """ Add locality info based on stops contained within the stop areas.
    """
    # Find stop areas with associated locality codes
    query = (
        db.session.query(
            models.StopArea.code.label("code"),
            models.StopPoint.locality_ref.label("ref"),
            db.func.count(models.StopPoint.locality_ref).label("count")
        ).select_from(models.StopPoint)
        .join(models.StopArea,
              models.StopArea.code == models.StopPoint.stop_area_ref)
        .group_by(models.StopArea.code, models.StopPoint.locality_ref)
    )
    # Find locality for each stop area that contain the most stops
    areas, ambiguous = _find_stop_area_mode(query.all(), "locality_ref")
    # if still ambiguous, measure distance between stop area and each locality
    # and add to above
    if ambiguous:
        add_areas = _find_locality_min_distance(ambiguous.keys())
        areas.extend(add_areas)

    with database_session():
        logger.info("Adding locality codes to stop areas")
        db.session.bulk_update_mappings(models.StopArea, areas)


def _set_tram_admin_area():
    """ Set admin area ref for tram stops and areas to be the same as their
        localities.
    """
    tram_area = "147"

    # Update stop points
    select_ref = (
        db.session.query(models.Locality.admin_area_ref)
        .filter(models.Locality.code == models.StopPoint.locality_ref)
    ).as_scalar()

    with database_session():
        logger.info("Updating tram stops with admin area ref")
        (db.session.query(models.StopPoint)
         .filter(models.StopPoint.admin_area_ref == tram_area)
         .update({models.StopPoint.admin_area_ref: select_ref},
                 synchronize_session=False)
        )

    # Find stop areas with associated admin area codes
    query = (
        db.session.query(
            models.StopArea.code.label("code"),
            models.StopPoint.admin_area_ref.label("ref"),
            db.func.count(models.StopPoint.admin_area_ref).label("count")
        ).select_from(models.StopPoint)
        .join(models.StopArea,
              models.StopArea.code == models.StopPoint.stop_area_ref)
        .filter(models.StopArea.admin_area_ref == tram_area)
        .group_by(models.StopArea.code, models.StopPoint.admin_area_ref)
    )
    areas, ambiguous = _find_stop_area_mode(query.all(), "admin_area_ref")

    with database_session():
        logger.info("Adding locality codes to stop areas")
        db.session.bulk_update_mappings(models.StopArea, areas)

    for area in ambiguous.items():
        logger.warning("Area %s: ambiguous admin areas %s" % area)


def _get_naptan_data(naptan_files, list_area_codes=None, out_file=None):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.

        :param naptan_files: Iterator for list of NaPTAN XML files
        :param list_area_codes: List of administrative area codes
        :param out_file: File path to write transformed data to, relative to
        the project directory. If None the data is returned as a XML
        ElementTree object
    """
    naptan_data = merge_xml(naptan_files)
    transform = et.parse(os.path.join(ROOT_DIR, NAPTAN_XSLT))
    ext = et.Extension(XSLTExtFunctions(), None, ns=NXB_EXT_URI)

    if list_area_codes:
        area_query = " or ".join(".='%s'" % a for a in list_area_codes)
        area_ref = "[n:AdministrativeAreaRef[%s]]" % area_query

        # Modify the XPath queries to filter by admin area
        xsl_names = {"xsl": transform.xpath("namespace-uri(.)")}
        for ref in ["stops", "areas"]:
            param = transform.xpath("//xsl:param[@name='%s']" % ref,
                                    namespaces=xsl_names)[0]
            param.attrib["select"] += area_ref

    logger.info("Applying XSLT to NaPTAN data")
    new_data = naptan_data.xslt(transform, extensions=ext)

    if out_file:
        new_data.write_output(os.path.join(ROOT_DIR, out_file))
    else:
        return new_data


def commit_naptan_data(archive=None, list_files=None):
    """ Convert NaPTAN data (stop points and areas) to database objects and
        commit them to the application database.

        :param archive: Path to zipped archive file for NaPTAN XML files.
        :param list_files: List of file paths for NaPTAN XML files.
    """
    downloaded = None
    atco_codes = get_atco_codes()
    if archive is not None and list_files is not None:
        raise ValueError("Can't specify both archive file and list of files.")
    elif archive is not None:
        iter_files = file_ops.iter_archive(archive)
    elif list_files is not None:
        iter_files = iter(list_files)
    else:
        downloaded = download_naptan_data(atco_codes)
        iter_files = file_ops.iter_archive(downloaded)

    # Get list of admin areas and localities from NPTG data
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

    _get_naptan_data(iter_files, area_codes, out_file=NAPTAN_XML)
    eval_stops = _NaPTANStops(local_codes)
    naptan = DBEntries(NAPTAN_XML)
    naptan.add("StopAreas/StopArea", models.StopArea, eval_stops.parse_areas)
    naptan.add("StopPoints/StopPoint", models.StopPoint,
               eval_stops.parse_points, indices=("naptan_code",))
    # Commit changes to database
    naptan.commit()
    # Remove all orphaned stop areas and add localities to other stop areas
    _remove_stop_areas()
    _set_stop_area_locality()
    _set_tram_admin_area()

    if downloaded is not None:
        logger.info("New file %r downloaded; can be deleted" % downloaded)
    logger.info("NaPTAN population done")
