"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import collections
import copy
from importlib.resources import open_binary
import functools
import operator
import os
import tempfile
import zipfile

from flask import current_app
import lxml.etree as et
import pyparsing as pp

from nextbus import db, models
from nextbus.populate import file_ops, utils


NAPTAN_URL = r"http://naptan.app.dft.gov.uk/DataRequest/Naptan.ashx"
IND_MAX_CHARS = 5
IND_MAX_WORDS = 2


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
    """ Finds the mode of references for each stop area.

        The query results must have 3 columns: primary key, foreign key
        reference and number of stop points within each area matching that
        reference, in that order.

        :param ref: Name of the reference column.
        :returns: Two lists; one to be to be used with `bulk_update_mappings`
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
    """ Finds the minimum distance between stop areas and localities for these
        with ambiguous localities.
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
                utils.logger.warning(f"Area {sa}: {dist:.0f} m away from {k}")

        # Else, check if only one locality matches min distance and set it
        if len(local_min) == 1:
            utils.logger.debug(f"Area {sa} set to locality {local_min[0]}, "
                               f"dist {min_dist:.0f} m")
            update_areas.append({"code": sa, "locality_ref": local_min[0]})
        else:
            utils.logger.warning(f"Area {sa}: ambiguous localities, {min_dist}")

    return update_areas


def _set_stop_area_locality():
    """ Add locality info based on stops contained within the stop areas. """
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

    for area, areas in ambiguous.items():
        utils.logger.warning(f"Area {area}: ambiguous admin areas {areas}")


def _iter_xml(source, **kw):
    """ Iterates over each element in a file.

        https://www.ibm.com/developerworks/xml/library/x-hiperfparse/
    """
    context = et.iterparse(source, **kw)
    for event, element in context:
        yield event, element
        if event == "end":
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]

    for m in context.error_log:
        utils.logger.info(m)


def _split_naptan_file(area_codes, source, directory):
    """ Takes file object for a XML file, iterate over and append to new files
        in directory.
    """
    utils.logger.info(f"Acquiring namespace for XML file {source.name!r}")
    source.seek(0)
    ns = ""
    for event, obj in _iter_xml(source, events=("start-ns", "end")):
        if event == "start-ns" and obj[0] == "":
            ns = "{" + obj[1] + "}"
            break

    stop_point = ns + "StopPoint"
    stop_area = ns + "StopArea"
    admin_area_ref = ns + "AdministrativeAreaRef"

    base_name = os.path.splitext(os.path.basename(source.name))[0]
    current_name = None
    data = None
    root = None

    utils.logger.info(f"Iterating over and splitting {source.name!r}")
    source.seek(0)
    for event, obj in _iter_xml(
        source,
        events=("end",),
        tag=(stop_point, stop_area)
    ):
        ref = obj.find(admin_area_ref)
        if ref is None or ref.text not in area_codes:
            continue

        new_name = f"{base_name}_{ref.text}.xml"
        if new_name != current_name:
            if root is not None:
                data.write(os.path.join(directory, current_name))
            current_name = new_name
            if current_name in os.listdir(directory):
                data = et.parse(os.path.join(directory, current_name))
                root = data.getroot()
            else:
                r = obj.getparent().getparent()
                root = et.Element(r.tag, r.attrib, r.nsmap)
                root.set("FileName", current_name)
                data = et.ElementTree(root)

        parent = obj.getparent()
        new = root.find(parent.tag)
        if new is None:
            new = et.SubElement(root, parent.tag, parent.attrib, parent.nsmap)

        new.append(copy.copy(obj))

    if root is not None:
        data.write(os.path.join(directory, current_name))


def split_naptan_data(areas, original, new):
    """ Splits large NaPTAN XML file into several smaller ones, grouped by admin
        area code and saved in a new archive.

        :param areas: List of admin area codes to split files by.
        :param original: Archive with original XML files.
        :param new: Path for new archive with split XML files.
    """
    area_codes = set(areas)
    utils.logger.info(f"Creating temporary directory and opening original "
                      f"archive {original!r}")
    with tempfile.TemporaryDirectory() as temp_d:
        for f in file_ops.iter_archive(original):
            _split_naptan_file(area_codes, f, temp_d)

        files = os.listdir(temp_d)
        utils.logger.info(f"Saving {len(files)} files to archive {new!r}")
        with zipfile.ZipFile(new, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(os.path.join(temp_d, f), f)


def commit_naptan_data(archive=None, list_files=None, split=True):
    """ Convert NaPTAN data (stop points and areas) to database objects and
        commit them to the application database.

        :param archive: Path to zipped archive file for NaPTAN XML files.
        :param list_files: List of file paths for NaPTAN XML files.
        :param split: Splits NaPTAN XML files in archive by admin area code. Has
        no effect if list_files is used.
    """
    # Get complete list of ATCO admin areas and localities from NPTG data
    with db.engine.connect() as conn:
        query_area = conn.execute(db.select([models.AdminArea.code]))
        query_local = conn.execute(db.select([models.Locality.code]))

        areas = [a[0] for a in query_area.fetchall()]
        localities = [local[0] for local in query_local.fetchall()]

    root = current_app.config["ROOT_DIRECTORY"]

    if not areas or not localities:
        raise ValueError("NPTG tables are not populated; stop point data "
                         "cannot be added without the required locality data. "
                         "Populate the database with NPTG data first.")

    downloaded = None
    if archive is not None and list_files is not None:
        raise ValueError("Can't specify both archive file and list of files.")
    elif archive is not None:
        path = archive
    elif list_files is not None:
        path = None
    else:
        path = downloaded = file_ops.download(
            NAPTAN_URL,
            directory=os.path.join(root, "temp"),
            params={"format": "xml"}
        )

    split_path = None
    if path is not None and split:
        split_path = os.path.join(root, "temp", "NaPTAN_split.zip")
        split_naptan_data(areas, path, split_path)
        path = split_path

    if path is not None:
        iter_files = file_ops.iter_archive(path)
    else:
        iter_files = iter(list_files)

    # Go through data and create objects for committing to database
    _setup_naptan_functions()

    with open_binary("nextbus.populate", "naptan.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))
    metadata = utils.reflect_metadata()
    delete = True
    for file_ in iter_files:
        file_name = file_.name if hasattr(file_, "name") else file_
        utils.logger.info(f"Parsing file {file_name!r}")
        utils.populate_database(
            utils.collect_xml_data(utils.xslt_transform(file_, xslt)),
            metadata=metadata,
            delete=delete
        )
        delete = False

    # Remove all orphaned stop areas and add localities to other stop areas
    _remove_stop_areas()
    _set_stop_area_locality()
    _set_tram_admin_area()

    if downloaded is not None:
        utils.logger.info(f"New file {downloaded!r} downloaded; can be deleted")
    if split_path is not None:
        utils.logger.info(f"New archive {split_path!r} created; can be deleted")
    utils.logger.info("NaPTAN population done")
