"""
Populate locality and stop point data with NPTG and NaPTAN datasets.
"""
import collections
import copy
import re
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
    """ Sets up XSLT extension functions to parse names and indicators for stop
        points.
    """
    ind_parser = _create_ind_parser()
    # Replace multiple spaces or no spaces with ' / '.
    name_regex = re.compile(r"\s{2,}|(?<=\w)/(?=\w)")

    @utils.xslt_text_func
    def parse_ind(_, indicator):
        """ Shortens indicator for display. """
        return ind_parser(indicator)

    @utils.xslt_text_func
    def replace_name(_, name):
        return name_regex.sub(" / ", name)


def _remove_stop_areas(connection):
    """ Remove all stop areas without associated stop points. """
    orphan_stop_areas = (
        db.select([models.StopArea.code])
        .select_from(
            models.StopArea.__table__
            .outerjoin(models.StopPoint,
                       models.StopArea.code == models.StopPoint.stop_area_ref)
        )
        .where(models.StopPoint.atco_code.is_(None))
        .alias("orphan_stop_areas")
    )

    utils.logger.info("Deleting orphaned stop areas")
    connection.execute(
        db.delete(models.StopArea)
        .where(models.StopArea.code.in_(orphan_stop_areas))
    )


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


def _find_locality_distance(connection, ambiguous_areas):
    """ Finds the minimum distance between stop areas and localities for these
        with ambiguous localities.
    """
    distance = db.func.sqrt(
        db.func.power(models.StopArea.easting - models.Locality.easting, 2) +
        db.func.power(models.StopArea.northing - models.Locality.northing, 2)
    )
    # Do another query over list of areas to find distance
    query_distances = connection.execute(
        db.select([
            models.StopArea.code.label("code"),
            models.Locality.code.label("locality"),
            distance.label("distance")
        ])
        .distinct(models.StopArea.code, models.Locality.code)
        .select_from(
            models.StopPoint.__table__
            .join(models.Locality,
                  models.StopPoint.locality_ref == models.Locality.code)
            .join(models.StopArea,
                  models.StopPoint.stop_area_ref == models.StopArea.code)
        )
        .where(models.StopPoint.stop_area_ref.in_(ambiguous_areas))
    )

    # Group by stop area and locality reference
    stop_areas = collections.defaultdict(dict)
    for row in query_distances:
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


def _set_stop_area_locality(connection):
    """ Add locality info based on stops contained within the stop areas. """
    # Find stop areas with associated locality codes
    with connection.begin():
        query_stop_areas = connection.execute(
            db.select([
                models.StopArea.code.label("code"),
                models.StopPoint.locality_ref.label("ref"),
                db.func.count(models.StopPoint.locality_ref).label("count")
            ])
            .select_from(
                models.StopArea.__table__
                .join(models.StopPoint,
                      models.StopArea.code == models.StopPoint.stop_area_ref)
            )
            .group_by(models.StopArea.code, models.StopPoint.locality_ref)
        )
        stop_areas = query_stop_areas.fetchall()
        # Find locality for each stop area that contain the most stops
        areas, ambiguous = _find_stop_area_mode(stop_areas, "locality_ref")

        # if still ambiguous, measure distance between stop area and each
        # locality and add to above
        if ambiguous:
            add_areas = _find_locality_distance(connection, ambiguous.keys())
            areas.extend(add_areas)

        utils.logger.info("Adding locality codes to stop areas")
        for a in areas:
            connection.execute(
                db.update(models.StopArea)
                .values({"locality_ref": a["locality_ref"]})
                .where(models.StopArea.code == a["code"])
            )


def _set_tram_admin_area(connection):
    """ Set admin area ref for tram stops and areas to be the same as their
        localities.
    """
    tram_area = "147"

    with connection.begin():
        # Update stop points
        admin_area_ref = (
            db.select([models.Locality.admin_area_ref])
            .where(models.Locality.code == models.StopPoint.locality_ref)
            .as_scalar()
        )

        utils.logger.info("Updating tram stops with admin area ref")
        connection.execute(
            db.update(models.StopPoint)
            .values({models.StopPoint.admin_area_ref: admin_area_ref})
            .where(models.StopPoint.admin_area_ref == tram_area)
        )

        # Find stop areas with associated admin area codes
        stop_areas = connection.execute(
            db.select([
                models.StopArea.code.label("code"),
                models.StopPoint.admin_area_ref.label("ref"),
                db.func.count(models.StopPoint.admin_area_ref).label("count")
            ])
            .select_from(
                models.StopArea.__table__
                .join(models.StopPoint,
                      models.StopArea.code == models.StopPoint.stop_area_ref)
            )
            .where(models.StopArea.admin_area_ref == tram_area)
            .group_by(models.StopArea.code, models.StopPoint.admin_area_ref)
        )
        areas, ambiguous = _find_stop_area_mode(stop_areas.fetchall(),
                                                "admin_area_ref")

        utils.logger.info("Adding locality codes to stop areas")
        for a in areas:
            connection.execute(
                db.update(models.StopArea)
                .values({"admin_area_ref": a["admin_area_ref"]})
                .where(models.StopArea.code == a["code"])
            )

        for area, areas in ambiguous.items():
            utils.logger.warning(f"Area {area}: ambiguous admin areas {areas}")


def _iter_xml(source, **kw):
    """ Iterates over each element in a file using SAX.

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


def _find_xml_namespace(source):
    """ Find the namespace for a XML file using SAX. """
    utils.logger.info(f"Acquiring namespace for {source.name!r}")
    source.seek(0)
    namespace = ""
    for event, obj in _iter_xml(source, events=("start-ns", "end")):
        if event == "start-ns" and obj[0] == "":
            namespace = obj[1]
            break
    source.seek(0)

    return namespace


def _split_naptan_file(area_codes, source, directory):
    """ Splits a NaPTAN XML file into multiple files and saved in a directory.

        :param area_codes: Admin area codes to split files by. Any areas not in
        list are ignored.
        :param source: A XML file.
        :param directory: Directory to save new files to.
    """
    ns = _find_xml_namespace(source)
    stop_point = "{" + ns + "}" + "StopPoint"
    stop_area = "{" + ns + "}" + "StopArea"
    admin_area_ref = "{" + ns + "}" + "AdministrativeAreaRef"

    base_name = os.path.splitext(os.path.basename(source.name))[0]
    current_name = None
    data = None
    root = None

    utils.logger.info(f"Splitting {source.name!r}")
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
                # Save recently accrued data to file before switching to a
                # different area
                data.write(os.path.join(directory, current_name))
            current_name = new_name
            # Open element tree from existing file or recreate from source
            if current_name in os.listdir(directory):
                data = et.parse(os.path.join(directory, current_name))
                root = data.getroot()
            else:
                r = obj.getparent().getparent()
                root = et.Element(r.tag, r.attrib, r.nsmap)
                root.set("FileName", current_name)
                data = et.ElementTree(root)

        # StopPoint and StopArea elements reside in StopPoints and StopAreas
        # collections respectively. Check if they exist and recreate from source
        parent = obj.getparent()
        coll = root.find(parent.tag)
        if coll is None:
            coll = et.SubElement(root, parent.tag, parent.attrib, parent.nsmap)

        coll.append(copy.copy(obj))

    if root is not None:
        data.write(os.path.join(directory, current_name))


def _split_naptan_data(areas, original, new):
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


def populate_naptan_data(connection, archive=None, list_files=None, split=True):
    """ Convert NaPTAN data (stop points and areas) to database objects and
        commit them to the application database.

        :param connection: Connection for population
        :param archive: Path to zipped archive file for NaPTAN XML files.
        :param list_files: List of file paths for NaPTAN XML files.
        :param split: Splits NaPTAN XML files in archive by admin area code. Has
        no effect if list_files is used.
    """
    # Get complete list of ATCO admin areas and localities from NPTG data
    query_area = connection.execute(db.select([models.AdminArea.code]))
    query_local = connection.execute(db.select([models.Locality.code]))
    areas = [a[0] for a in query_area]
    localities = [local[0] for local in query_local]

    if not areas or not localities:
        raise ValueError("NPTG tables are not populated; stop point data "
                         "cannot be added without the required locality data. "
                         "Populate the database with NPTG data first.")

    temp = current_app.config.get("TEMP_DIRECTORY")
    if not temp:
        raise ValueError("TEMP_DIRECTORY is not defined.")

    if archive is not None and list_files is not None:
        raise ValueError("Can't specify both archive file and list of files.")
    elif archive is not None:
        path = archive
    elif list_files is not None:
        path = None
    else:
        path = file_ops.download(
            NAPTAN_URL,
            directory=temp,
            params={"format": "xml"}
        )

    if path is not None and split:
        split_path = os.path.join(temp, "NaPTAN_split.zip")
        _split_naptan_data(areas, path, split_path)
        path = split_path

    if path is not None:
        iter_files = file_ops.iter_archive(path)
    else:
        iter_files = iter(list_files)

    # Go through data and create objects for committing to database
    _setup_naptan_functions()

    metadata = utils.reflect_metadata(connection)
    with open_binary("nextbus.populate", "naptan.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))

    deleted = False
    for i, file_ in enumerate(iter_files):
        file_name = file_.name if hasattr(file_, "name") else file_
        utils.logger.info(f"Parsing file {file_name!r}")
        utils.populate_database(
            connection,
            utils.collect_xml_data(utils.xslt_transform(file_, xslt)),
            metadata=metadata,
            delete=not deleted
        )
        deleted = True


def process_naptan_data(connection):
    # Remove all orphaned stop areas and add localities to other stop areas
    _remove_stop_areas(connection)
    _set_stop_area_locality(connection)
    _set_tram_admin_area(connection)
