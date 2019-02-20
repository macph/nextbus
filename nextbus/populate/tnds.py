"""
Populate bus route and timetable data from TNDS.
"""
import ftplib
import os
import re

from flask import current_app
import lxml.etree as et

from definitions import ROOT_DIR
from nextbus import db, models
from nextbus.populate import file_ops, utils


TNDS_URL = r"ftp.tnds.basemap.co.uk"
TNDS_XSLT = r"nextbus/populate/tnds.xslt"
TNDS_ROLLOVER = 100000


def _get_regions():
    """ Get list of regions in database excluding GB. If no regions are found,
        a ValueError is raised.
    """
    with utils.database_connection() as conn:
        query_regions = conn.execute(db.select([models.Region.code])
                                     .where(models.Region.code != "GB"))
    regions = [r[0] for r in query_regions]

    if not regions:
        raise ValueError("NPTG data not populated yet.")

    return regions


def download_tnds_files():
    """ Download TNDS files from FTP server. """
    user = current_app.config.get("TNDS_USERNAME")
    password = current_app.config.get("TNDS_PASSWORD")
    if not user or not password:
        raise ValueError("The application config requires an username and "
                         "password to access the TNDS FTP server. See the "
                         "Traveline website for more details.")

    regions = _get_regions()
    paths = {}
    utils.logger.info("Opening FTP connection to %r with credentials" %
                      TNDS_URL)
    with ftplib.FTP(TNDS_URL, user=user, passwd=password) as ftp:
        for region in regions:
            file_name = region + ".zip"
            file_path = os.path.join(ROOT_DIR, "temp", file_name)
            utils.logger.info("Downloading file %r from %r" %
                              (file_name, TNDS_URL))
            with open(file_path, "wb") as file_:
                ftp.retrbinary("RETR " + file_name, file_.write)
            paths[region] = file_path

    return paths


class IndexList(object):
    """ Unique list using a dict with keys as the list and values its indices.
    """
    def __init__(self, iterable=None, initial=0):
        self._map = {}
        self._current = self._initial = initial
        if iterable is not None:
            for i in iterable:
                self.add(i)

    def __repr__(self):
        items = ", ".join(repr(i) for i in self)
        return "<IndexList(%s, initial=%s)>" % (items, self._initial)

    def __len__(self):
        return len(self._map)

    def __contains__(self, item):
        return item in self._map

    def __getitem__(self, index):
        for k, j in self._map.items():
            if index == j:
                return k
        else:
            raise IndexError("Index out of range")

    def __iter__(self):
        return iter(sorted(self._map, key=self._map.get))

    def add(self, item=None):
        """ Adds item to list, returning its index.

            :param item: Item being added. If it is None, the index is
            incremented but the list won't be expanded.
            :returns: Index of item.
        """
        if item is None:
            new = self._current
            self._current += 1
        elif item not in self._map:
            new = self._map[item] = self._current
            self._current += 1
        else:
            new = self._map[item]

        return new

    def get(self, item):
        """ Gets index of an item or None if it does not exist. """
        if item is None:
            raise ValueError("'None' not accepted as key.")

        return self._map.get(item)


class RowIds(object):
    """ Create XSLT functions to assign each row for journey patterns, sections
        and links an unique ID.

        A service in the TNDS dataset has its own XML file or split up across
        several files, with the associated journey patterns having unique IDs
        within only these documents.
    """
    def __init__(self, check_existing=True):
        self._id = {}
        self.existing = check_existing

        # Register XSLT functions
        utils.xslt_text_func(self.add_id)
        utils.xslt_text_func(self.get_id)

    def _get_sequence(self, model_name):
        """ Check database to find max value to start from or use 1. """
        start = 1
        if self.existing:
            # Get maximum ID integer from table and start off from there
            model = getattr(models, model_name)
            query = db.select([db.func.max(model.id)])
            max_ = db.engine.execute(query).scalar()

            start = max_ + 1 if max_ is not None else start

        return start

    def add_id(self, _, name, *ids):
        """ Adds IDs (eg file name, code) to list, returning an integer ID. """
        if name not in self._id:
            # Find the initial sequence and set up list
            initial = self._get_sequence(name)
            utils.logger.info("Setting sequence for %s to %d" % (name, initial))

            self._id[name] = IndexList(initial=initial)

        new_id = self._id[name].add(ids if ids else None)
        utils.logger.debug("Added ID %d for %r and identifiers %r" %
                           (new_id, name, ids))

        return new_id

    def get_id(self, _, name, *ids):
        """ Gets integer ID for IDs (eg file name, code) """
        if name not in self._id or ids not in self._id[name]:
            raise ValueError("IDs %r does not exist for model %r." %
                             (ids, name))

        got_id = self._id[name].get(ids)
        utils.logger.debug("Retrieved ID %d for %r and identifiers %r" %
                           (got_id, name, ids))

        return got_id


@utils.xslt_text_func
def format_description(_, text):
    if text.isupper():
        text = utils.capitalize(None, text)

    places = " ".join(text.split())
    places = places.split(" - ")
    new_places = []

    sep = re.compile(r"(.+\S),(\S.+)")
    for p in places:
        separated = sep.search(p)
        new_places.append(separated.group(2) if separated else p)

    return " – ".join(new_places)


@utils.xslt_text_func
def format_destination(_, text):
    if text is not None and text.isupper():
        text = utils.capitalize(None, text)

    return text


@utils.xslt_func
def days_week(_, nodes=None):
    """ Gets days of week from a RegularDayType element.

        Returned as an integer with Monday-Sunday corresponding to bits 1-7. If
        nodes is None Monday-Friday is returned as the default.
    """
    days = {
        "Monday":           0b00000010,
        "Tuesday":          0b00000100,
        "Wednesday":        0b00001000,
        "Thursday":         0b00010000,
        "Friday":           0b00100000,
        "Saturday":         0b01000000,
        "Sunday":           0b10000000,
        "Weekend":          0b11000000,
        "MondayToFriday":   0b00111110,
        "MondayToSaturday": 0b01111110,
        "NotSaturday":      0b10111110,
        "MondayToSunday":   0b11111110
    }

    try:
        element = nodes[0]
    except IndexError:
        element = None  # No element returned
    except TypeError:
        element = nodes  # Single element instead of a list

    if element is not None:
        week = 0
        ns = {"txc": element.xpath("namespace-uri(.)")}
        for d in element.xpath("txc:DaysOfWeek/*", namespaces=ns):
            tag = et.QName(d).localname
            week |= days.get(tag, 0)
    else:
        # Default is Monday to Friday
        week = days["MondayToFriday"]

    return week


@utils.xslt_func
def weeks_month(_, nodes):
    """ Gets weeks of month from a PeriodicDayType element.

        Returned as an integer with first to fifth weeks corresponding to bits
        0-4. If no weeks are found, None is returned.
    """
    weeks = {
        "first":  0b00001,
        "second": 0b00010,
        "third":  0b00100,
        "fourth": 0b01000,
        "fifth":  0b10000,
    }

    try:
        element = nodes[0]
    except IndexError:
        element = None

    if element is None:
        return

    ns = {"txc": element.xpath("namespace-uri(.)")}
    month = 0
    for w in element.xpath("//txc:WeekNumber", namespaces=ns):
        try:
            num = 1 << (int(w.text) - 1)
        except (TypeError, ValueError):
            num = weeks[w.text.lower()]
        month |= num

    return month if month > 0 else None


@utils.xslt_func
def bank_holidays(_, nodes):
    """ Gets bank holidays from a DaysOfOperation or DaysOfNonOperation
        element within a BankHolidayOperation element for a Journey.
    """
    holidays = {
        "AllBankHolidays":                  0b1111111111111110,
        "AllHolidaysExceptChristmas":       0b0000000111111110,
        "NewYearsDay":                      0b0000000000000010,
        "Jan2ndScotland":                   0b0000000000000100,
        "GoodFriday":                       0b0000000000001000,
        "HolidayMondays":                   0b0000000111110000,
        "EasterMonday":                     0b0000000000010000,
        "MayDay":                           0b0000000000100000,
        "SpringBank":                       0b0000000001000000,
        "LateSummerBankHolidayNotScotland": 0b0000000010000000,
        "AugustBankHolidayScotland":        0b0000000100000000,
        "Christmas":                        0b0000011000000000,
        "ChristmasDay":                     0b0000001000000000,
        "BoxingDay":                        0b0000010000000000,
        "DisplacementHolidays":             0b0011100000000000,
        "ChristmasDayHoliday":              0b0000100000000000,
        "BoxingDayHoliday":                 0b0001000000000000,
        "NewYearsDayHoliday":               0b0010000000000000,
        "EarlyRunOffDays":                  0b1100000000000000,
        "ChristmasEve":                     0b0100000000000000,
        "NewYearsEve":                      0b1000000000000000
    }

    try:
        element = nodes[0]
    except IndexError:
        element = None  # No element returned
    except TypeError:
        element = nodes  # Single element instead of a list

    hols = 0
    if element is not None:
        ns = {"txc": element.xpath("namespace-uri(.)")}
        for d in element.xpath("./*", namespaces=ns):
            tag = et.QName(d).localname
            hols |= holidays.get(tag, 0)

    return hols


def setup_tnds_functions():
    """ Finds all existing stop points in database, setting up XSLT functions.
    """
    with utils.database_connection() as conn:
        query_operators = conn.execute(db.select([models.Operator.code]))
        query_stops = conn.execute(db.select([models.StopPoint.atco_code]))
    set_operators = {o.code for o in query_operators}
    set_stops = {c.atco_code for c in query_stops}
    set_not_exists = set()

    if not set_stops:
        raise ValueError("No stop points were found. The TNDS dataset requires "
                         "the database to be populated from NaPTAN data first.")
    if not set_operators:
        raise ValueError("No operators were found. The TNDS dataset requires "
                         "the database to be populated from NOC data first.")

    @utils.xslt_text_func
    def stop_exists(_, code):
        """ Check if stop point exists. """
        nonlocal set_not_exists
        exists = code in set_stops
        if not exists and code not in set_not_exists:
            set_not_exists.add(code)
            utils.logger.warning("Stop code %r does not exist." % code)

        return exists


def _execute_with_log(connection, statement, message):
    """ Executes an insert, update or delete statement and logs with message.

        Messages should have two format characters - first one with number of
        rows updated/deleted/added and the second the plural 's' character.
    """
    result = connection.execute(statement)
    count = result.rowcount
    utils.logger.info(message % (count, "s" if count != 1 else ""))


def _delete_empty_services():
    """ Delete services and associated operators if all stop point references
        are null - eg when including a metro route where all stop points are
        not in the existing database.
    """
    empty_patterns = ~(
        db.session.query(models.JourneyLink)
        .filter(models.JourneyLink.pattern_ref == models.JourneyPattern.id,
                models.JourneyLink.stop_point_ref.isnot(None))
        .exists()
    )
    empty_services = ~(
        db.session.query(models.JourneyPattern)
        .filter(models.JourneyPattern.service_ref == models.Service.id)
        .exists()
    )
    empty_local_operators = ~(
        db.session.query(models.JourneyPattern)
        .filter(models.JourneyPattern.region_ref
                == models.LocalOperator.region_ref,
                models.JourneyPattern.local_operator_ref
                == models.LocalOperator.code)
        .exists()
    )
    empty_operators = ~(
        db.session.query(models.LocalOperator)
        .filter(models.LocalOperator.operator_ref == models.Operator.code)
        .exists()
    )
    empty_organisations = ~(
        db.session.query(models.Organisations)
        .filter(models.Organisations.org_ref == models.Organisation.code)
        .exists()
    )

    def delete(model, where):
        return model.__table__.delete().where(where)

    with utils.database_connection() as conn:
        # All associated journey links and journeys will be deleted too
        _execute_with_log(conn, delete(models.JourneyPattern, empty_patterns),
                          "%d journey pattern%s without stop point references "
                          "deleted")
        _execute_with_log(conn, delete(models.Service, empty_services),
                          "%d service%s without journey patterns deleted")
        _execute_with_log(conn, delete(models.Locality, empty_services),
                          "%d service%s without journey patterns deleted")
        _execute_with_log(conn,
                          delete(models.LocalOperator, empty_local_operators),
                          "%d local operator%s without services deleted")
        _execute_with_log(conn, delete(models.LocalOperator, empty_operators),
                          "%d operator%s without local operators deleted")
        _execute_with_log(conn,
                          delete(models.Organisation, empty_organisations),
                          "%d organisation%s without journeys deleted")


def _compare_arrays(array0, array1):
    """ Returns expression comparing two arrays by dividing the length of the
        intersected arrays with the least of the two array lengths.
    """
    length0 = db.func.cardinality(array0)
    length1 = db.func.cardinality(array1)

    # Correlation and labelling prevents the interior terms appearing in FROM
    # clause - see https://stackoverflow.com/questions/40366275
    intersect = db.func.array(
        db.select([db.func.unnest(array0)]).correlate(array0.table)
        .intersect(db.select([db.func.unnest(array1)]).correlate(array1.table))
        .label("matched")
    )
    compare = (
        db.cast(db.func.cardinality(intersect), db.Float) /
        db.func.least(length0, length1)
    )

    # Avoid division by zero by testing cardinality of both arrays
    return db.case([(db.and_(length0 > 0, length1 > 0), compare)], else_=0)


def _array_agg(col):
    """ Expression for aggregated array with distinct and non-null values. """
    return db.func.array_remove(db.func.array_agg(db.distinct(col)), None)


def _merge_services():
    """ Merge all services if they share the same line and at least half of
        stops within their journey patterns.
    """
    service = models.Service.__table__
    pattern = models.JourneyPattern.__table__
    link = models.JourneyLink.__table__

    # Create temporary table to hold all services and their associated stops
    stops = db.Table(
        "service_stops",
        db.Column("id", db.Integer),
        db.Column("line", db.Text),
        db.Column("stops", db.ARRAY(db.Text, dimensions=1)),
        db.Column("outbound", db.ARRAY(db.Text, dimensions=1)),
        db.Column("inbound", db.ARRAY(db.Text, dimensions=1)),
        prefixes=["TEMPORARY"],
        postgresql_on_commit="DROP"
    )

    insert_stops = stops.insert().from_select(
        ["id", "line", "stops", "outbound", "inbound"],
        db.select([
            service.c.id,
            service.c.line,
            _array_agg(link.c.stop_point_ref),
            _array_agg(db.case([(pattern.c.direction, link.c.stop_point_ref)],
                               else_=None)),
            _array_agg(db.case([(~pattern.c.direction, link.c.stop_point_ref)],
                               else_=None)),
        ])
        .select_from(service
                     .join(pattern, pattern.c.service_ref == service.c.id)
                     .join(link, link.c.pattern_ref == pattern.c.id))
        .group_by(service.c.id)
    )

    # Using table of services and stops, find intersecting stops for every pair
    # of services. Then filter pairs of services whose stops make up more than
    # half of intersecting stops they share.
    pairs = db.Table(
        "service_pairs",
        db.Column("id0", db.Integer),
        db.Column("id1", db.Integer),
        prefixes=["TEMPORARY"],
        postgresql_on_commit="DROP"
    )

    s0, s1 = stops.alias("s0"), stops.alias("s1")
    insert_pairs = pairs.insert().from_select(
        ["id0", "id1"],
        db.select([s0.c.id, s1.c.id])
        .select_from(s0)
        .select_from(s1)
        .where(db.and_(s0.c.line == s1.c.line, s0.c.id < s1.c.id,
                       _compare_arrays(s0.c.stops, s1.c.stops) > 0.5))
    )

    # Using a recursive CTE, find all original services and other services which
    # share more than half their stops.
    duplicates = db.Table(
        "service_duplicates",
        db.Column("original", db.Integer),
        db.Column("other", db.Integer),
        prefixes=["TEMPORARY"],
        postgresql_on_commit="DROP"
    )

    pairs_alias = pairs.alias("sp0")
    other_ids = db.exists(
        db.select([1])
        .select_from(pairs_alias)
        .where(pairs.c.id0 == pairs_alias.c.id1)
    )
    merge = (
        db.select([pairs.c.id0.label("original"), pairs.c.id1.label("next")])
        .select_from(pairs)
        .where(~other_ids)
        .cte("service_merge", recursive=True)
    )
    merge = merge.union_all(
        db.select([merge.c.original, pairs.c.id1.label("next")])
        .select_from(pairs.join(merge, pairs.c.id0 == merge.c.next))
    )

    insert_duplicates = duplicates.insert().from_select(
        ["original", "other"],
        db.select([merge.c.original, merge.c.next]).distinct()
        .select_from(merge)
    )

    # Use more CTEs to find stops for each duplicate service, filtered by
    # direction, we can flip journey pattern directions while merging them
    # such that all journey patterns have roughly the same sequence of stops.
    dup_directions = db.Table(
        "service_duplicate_directions",
        db.Column("original", db.Integer),
        db.Column("other", db.Integer),
        db.Column("swap", db.Boolean),
        prefixes=["TEMPORARY"],
        postgresql_on_commit="DROP"
    )

    directions = (
        db.select([
            duplicates.c.original,
            duplicates.c.other,
            _compare_arrays(s0.c.outbound, s1.c.outbound).label("intersect_0"),
            _compare_arrays(s0.c.inbound, s1.c.inbound).label("intersect_1"),
            _compare_arrays(s0.c.outbound, s1.c.inbound).label("intersect_2"),
            _compare_arrays(s0.c.inbound, s1.c.outbound).label("intersect_3")
        ])
        .select_from(
            duplicates
            .join(s0, duplicates.c.original == s0.c.id)
            .join(s1, duplicates.c.other == s1.c.id)
        )
        .cte("service_pairs_directions")
    )

    insert_dup_directions = dup_directions.insert().from_select(
        ["original", "other", "swap"],
        db.select([
            directions.c.original,
            directions.c.other,
            db.or_(db.and_(directions.c.intersect_2 > directions.c.intersect_0,
                           directions.c.intersect_2 > 0.5),
                   db.and_(directions.c.intersect_3 > directions.c.intersect_1,
                           directions.c.intersect_3 > 0.5))
        ])
        .select_from(directions)
    )

    # Update all patterns' service refs to the original services
    update_patterns = (
        pattern.update()
        .values(
            service_ref=dup_directions.c.original,
            direction=db.case([(dup_directions.c.swap, ~pattern.c.direction)],
                              else_=pattern.c.direction)
        )
        .where(pattern.c.service_ref == dup_directions.c.other)
    )

    # Delete all other services
    other_ids = db.select([dup_directions.c.other])
    delete_services = service.delete().where(service.c.id.in_(other_ids))

    # Do everything within a transaction - temp tables will be dropped on commit
    with utils.database_connection() as conn:
        utils.logger.info("Finding all services sharing line labels and stops")
        stops.create(conn)
        conn.execute(insert_stops)

        pairs.create(conn)
        conn.execute(insert_pairs)

        duplicates.create(conn)
        conn.execute(insert_duplicates)

        dup_directions.create(conn)
        conn.execute(insert_dup_directions)

        _execute_with_log(conn, update_patterns,
                          "%d journey pattern%s updated to new service refs")

        _execute_with_log(conn, delete_services,
                          "%d duplicate service%s deleted")


def _fill_description():
    """ Find all services without descriptions and replace with localities
        served using the graph diameter.
    """
    pass


def _get_tnds_transform():
    """ Uses XSLT to convert TNDS XML data into several separate datasets. """
    tnds_xslt = et.parse(os.path.join(ROOT_DIR, TNDS_XSLT))
    transform = et.XSLT(tnds_xslt)

    return transform


def _commit_tnds_region(transform, archive, region, delete=False,
                        rollover=TNDS_ROLLOVER):
    """ Transforms each XML file and commit data to DB. """
    tnds = utils.PopulateData()
    str_region = transform.strparam(region)

    del_ = delete
    # We don't want to delete any NOC data if they have been added
    excluded = models.Operator, models.LocalOperator

    for i, file_ in enumerate(file_ops.iter_archive(archive)):
        utils.logger.info("Parsing file %r" % os.path.join(archive, file_.name))
        data = et.parse(file_)
        file_name = transform.strparam(file_.name)

        try:
            new_data = transform(data, region=str_region, file=file_name)
        except et.XSLTError as err:
            for error_message in getattr(err, "error_log"):
                utils.logger.error(error_message)
            raise

        tnds.add_from(new_data)

        if tnds.total() > rollover:
            tnds.commit(delete=del_, exclude=excluded, clear=True)
            del_ = False

    # Commit rest of entries
    tnds.commit(delete=del_, exclude=excluded)


def commit_tnds_data(directory=None, delete=True):
    """ Commits TNDS data to database.

        :param directory: Directory where zip files with TNDS XML documents and
        named after region codes are contained. If None, they will be
        downloaded.
        :param delete: Truncate all data from TNDS tables before populating.
    """
    if directory is None:
        # Download required files and get region code from each filename
        data = download_tnds_files()
    else:
        regions = _get_regions()
        data = {}
        for r in regions:
            file_ = r + ".zip"
            path = os.path.join(directory, file_)
            if os.path.exists(path):
                data[r] = path
            else:
                utils.logger.warning("Archive %r not found in directory %r." %
                                     (file_, directory))

    if not data:
        raise ValueError("No files were passed - either specified directory "
                         "did not contain any suitable archives or they failed "
                         "to be downloaded.")

    transform = _get_tnds_transform()
    setup_tnds_functions()
    RowIds(check_existing=not delete)

    del_ = delete
    for region, archive in data.items():
        _commit_tnds_region(transform, archive, region, delete=del_)
        del_ = False

    _delete_empty_services()
    _merge_services()
