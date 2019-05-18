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
from nextbus.populate import file_ops, utils


NAPTAN_URL = r"http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx"
NAPTAN_XSLT = r"nextbus/populate/naptan.xslt"
NAPTAN_XML = r"temp/naptan_data.xml"
IND_MAX_CHARS = 5
IND_MAX_WORDS = 2


def download_naptan_data():
    """ Downloads NaPTAN data from the DfT. Comes in a zipped file.
    """
    return file_ops.download(NAPTAN_URL, directory="temp",
                             params={"format": "xml"})


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
        combined = functools.reduce(operator.or_,
                                    map(pp.CaselessKeyword, words))
        if replace is not None:
            combined = combined.setParseAction(pp.replaceWith(replace))

        return combined

    def action_upper(tokens):
        """ Uppercase the matched substring. """
        return tokens[0].upper()

    def action_abbrv(tokens):
        """ Abbreviates a number of words. """
        return "".join(word[0].upper() for word in tokens)

    def action_arrow(tokens):
        """ Adds arrow to matched substring. """
        return "->" + tokens[0].upper()

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
        kw_one_of("on", replace="on"),
        kw_one_of("to", replace="to")
    ])
    # Exclude common words, eg 'Stop' or 'Bay'.
    excluded_words = kw_one_of(
        "and", "bay", "gate", "no", "platform", "stance", "stances",
        "stand", "stop", "the", "to"
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


def _setup_naptan_functions():
    """ Sets up XSLT extension functions to parse indicators for stop points.
    """
    ind_parser = _create_ind_parser()

    @utils.xslt_text_func
    def parse_ind(_, indicator):
        """ Shortens indicator for display. """
        return ind_parser(indicator)


def _remove_stop_areas():
    """ Remove all stop areas without associated stop points. """
    query_stop_area_del = (
        db.session.query(models.StopArea.code)
        .outerjoin(models.StopArea.stop_points)
        .filter(models.StopPoint.atco_code.is_(None))
        .subquery()
    )

    with utils.database_session():
        utils.logger.info("Deleting orphaned stop areas")
        query = (
            models.StopArea.query
            .filter(models.StopArea.code.in_(query_stop_area_del))
        )
        query.delete(synchronize_session="fetch")


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
        )
        .select_from(models.StopPoint)
        .distinct(models.StopArea.code, models.Locality.code)
        .join(models.StopPoint.locality)
        .join(models.StopPoint.stop_area)
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
        # Find all localities with minimum distance from stop area
        local_min = [k for k, v in local.items() if v == min_dist]

        # Check if associated localities are far away - may be wrong locality
        for k, dist in local.items():
            if dist > 2 * min_dist and dist > 1000:
                utils.logger.warning("Area %s: %.0f m away from %s" %
                                     (sa, dist, k))

        # Else, check if only one locality matches min distance and set it
        if len(local_min) == 1:
            utils.logger.debug("Area %s set to locality %s, dist %.0f m" %
                               (sa, local_min[0], min_dist))
            update_areas.append({"code": sa, "locality_ref": local_min[0]})
        else:
            utils.logger.warning("Area %s: ambiguous localities %s" %
                                 (sa, min_dist))

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
        )
        .select_from(models.StopPoint)
        .join(models.StopPoint.stop_area)
        .group_by(models.StopArea.code, models.StopPoint.locality_ref)
    )
    # Find locality for each stop area that contain the most stops
    areas, ambiguous = _find_stop_area_mode(query.all(), "locality_ref")

    # if still ambiguous, measure distance between stop area and each locality
    # and add to above
    if ambiguous:
        add_areas = _find_locality_min_distance(ambiguous.keys())
        areas.extend(add_areas)

    with utils.database_session():
        utils.logger.info("Adding locality codes to stop areas")
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
        .as_scalar()
    )

    with utils.database_session():
        utils.logger.info("Updating tram stops with admin area ref")
        query = (
            db.session.query(models.StopPoint)
            .filter(models.StopPoint.admin_area_ref == tram_area)
        )
        query.update({models.StopPoint.admin_area_ref: select_ref},
                     synchronize_session=False)

    # Find stop areas with associated admin area codes
    query = (
        db.session.query(
            models.StopArea.code.label("code"),
            models.StopPoint.admin_area_ref.label("ref"),
            db.func.count(models.StopPoint.admin_area_ref).label("count")
        )
        .select_from(models.StopPoint)
        .join(models.StopPoint.stop_area)
        .filter(models.StopArea.admin_area_ref == tram_area)
        .group_by(models.StopArea.code, models.StopPoint.admin_area_ref)
    )
    areas, ambiguous = _find_stop_area_mode(query.all(), "admin_area_ref")

    with utils.database_session():
        utils.logger.info("Adding locality codes to stop areas")
        db.session.bulk_update_mappings(models.StopArea, areas)

    for area in ambiguous.items():
        utils.logger.warning("Area %s: ambiguous admin areas %s" % area)


def _get_naptan_data(naptan_file):
    """ Parses NaPTAN XML data and returns lists of stop points and stop areas
        within the specified admin areas.

        :param naptan_file: File-like object or path for a source XML file
        :returns: Transformed data as a XML ElementTree object
    """
    naptan_data = et.parse(naptan_file)
    xslt_data = et.parse(os.path.join(ROOT_DIR, NAPTAN_XSLT))
    transform = et.XSLT(xslt_data)

    try:
        new_data = transform(naptan_data)
    except (et.XSLTParseError, et.XSLTApplyError) as err:
        for error_message in getattr(err, "error_log"):
            utils.logger.error(error_message)
        raise

    return new_data


def commit_naptan_data(archive=None, list_files=None):
    """ Convert NaPTAN data (stop points and areas) to database objects and
        commit them to the application database.

        :param archive: Path to zipped archive file for NaPTAN XML files.
        :param list_files: List of file paths for NaPTAN XML files.
    """
    # Get complete list of ATCO admin areas and localities from NPTG data
    with utils.database_connection() as conn:
        query_area = conn.execute(db.select([models.AdminArea.code]))
        query_local = conn.execute(db.select([models.Locality.code]))

    areas = query_area.fetchall()
    localities = query_local.fetchall()
    if not areas or not localities:
        raise ValueError("NPTG tables are not populated; stop point data "
                         "cannot be added without the required locality data. "
                         "Populate the database with NPTG data first.")

    downloaded = None
    if archive is not None and list_files is not None:
        raise ValueError("Can't specify both archive file and list of files.")
    elif archive is not None:
        iter_files = file_ops.iter_archive(archive)
    elif list_files is not None:
        iter_files = iter(list_files)
    else:
        downloaded = download_naptan_data()
        iter_files = file_ops.iter_archive(downloaded)

    # Go through data and create objects for committing to database
    _setup_naptan_functions()
    naptan = utils.PopulateData()

    for file_ in iter_files:
        file_name = file_.name if hasattr(file_, "name") else file_
        utils.logger.info("Parsing file %r" % file_name)
        naptan.add_from(_get_naptan_data(file_))

    naptan.commit(delete=True)
    # Remove all orphaned stop areas and add localities to other stop areas
    _remove_stop_areas()
    _set_stop_area_locality()
    _set_tram_admin_area()

    if downloaded is not None:
        utils.logger.info("New file %r downloaded; can be deleted" %
                          downloaded)
    utils.logger.info("NaPTAN population done")
