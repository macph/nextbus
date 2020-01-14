"""
Populate bus route and timetable data from TNDS.
"""
import collections
import ftplib
import os
import re
from importlib.resources import open_binary

from flask import current_app
import lxml.etree as et

from nextbus import db, models
from nextbus.populate import file_ops, utils


TNDS_URL = r"ftp.tnds.basemap.co.uk"

BRACKETS = re.compile(r"\((.*)\)")
SPLIT_PLACES = re.compile(r"\s+-\s+|-\s+|\s+-")
FIND_EXTRA = re.compile(r"(.+\S),(\S.+)")


def _get_regions(connection):
    """ Get list of regions in database excluding GB. If no regions are found,
        a ValueError is raised.
    """
    query_regions = connection.execute(
        db.select([models.Region.code]).where(models.Region.code != "GB")
    )
    regions = [r[0] for r in query_regions]

    if not regions:
        raise ValueError("NPTG data not populated yet.")

    return regions


def _download_tnds_files(regions):
    """ Download TNDS files from FTP server. """
    if not regions:
        return {}

    user = current_app.config.get("TNDS_USERNAME")
    password = current_app.config.get("TNDS_PASSWORD")
    if not user or not password:
        raise ValueError("The application config requires an username and "
                         "password to access the TNDS FTP server. See the "
                         "Traveline website for more details.")

    paths = {}
    utils.logger.info(f"Opening FTP connection {TNDS_URL!r} with credentials")
    with ftplib.FTP(TNDS_URL, user=user, passwd=password) as ftp:
        for region in regions:
            file_name = region + ".zip"
            file_path = os.path.join(
                current_app.config["ROOT_DIRECTORY"],
                "temp",
                file_name
            )
            utils.logger.info(f"Downloading file {file_name!r}")
            with open(file_path, "wb") as file_:
                ftp.retrbinary("RETR " + file_name, file_.write)
            paths[region] = file_path

    return paths


class IndexList:
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
        return f"<IndexList({items}, initial={self._initial})>"

    def __len__(self):
        return len(self._map)

    def __contains__(self, item):
        return item in self._map

    def __getitem__(self, index):
        for k, j in self._map.items():
            if index == j:
                return k
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

    def clear(self):
        """ Clear all records in IndexList. """
        self._map.clear()


class RowIds:
    """ Create XSLT functions to assign each row for journey patterns, sections
        and links an unique ID.

        A service in the TNDS dataset has its own XML file or split up across
        several files, with the associated journey patterns having unique IDs
        within only these documents.
    """
    def __init__(self, connection, check_existing=True):
        self._id = {}
        self._conn = connection
        self.existing = check_existing

        # Register XSLT functions
        utils.xslt_text_func(self.add_id)
        utils.xslt_text_func(self.get_id)

    def _get_sequence(self, model_name):
        """ Check database to find max value to start from or use 1. """
        start = 1
        model = getattr(models, model_name, None)
        if self.existing and model is not None:
            # Get maximum ID integer from table and start off from there
            query = db.select([db.func.max(model.id)])
            max_ = self._conn.execute(query).scalar()
            start = max_ + 1 if max_ is not None else start

        return start

    def add_id(self, _, name, *ids):
        """ Adds IDs (eg file name, code) to list, returning an integer ID. """
        if name not in self._id:
            # Find the initial sequence and set up list
            initial = self._get_sequence(name)
            utils.logger.info(f"Setting sequence for {name} to {initial}")

            self._id[name] = IndexList(initial=initial)

        new_id = self._id[name].add(tuple(map(str, ids)) if ids else None)
        utils.logger.debug(f"Added ID {new_id} for {name!r} and identifiers "
                           f"{ids!r}")

        return new_id

    def get_id(self, _, name, *ids):
        """ Gets integer ID for IDs (eg file name, code) """
        if name not in self._id or ids not in self._id[name]:
            raise ValueError(f"IDs {ids!r} does not exist for model {name!r}.")

        got_id = self._id[name].get(tuple(map(str, ids)))
        utils.logger.debug(f"Retrieved ID {got_id} for {name} and identifiers "
                           f"{ids!r}")

        return got_id

    def clear(self):
        """ Clear all stored values in each IndexList. """
        for ids in self._id.values():
            ids.clear()


@utils.xslt_text_func
def format_description(_, text):
    if text.isupper():
        text = utils.capitalize(None, text)

    places = SPLIT_PLACES.split(" ".join(text.split()))
    new_places = []
    for p in places:
        # Some service descriptions have extra data before origin/destination
        # which are mostly irrelevant
        separated = FIND_EXTRA.search(p)
        new_places.append(separated.group(2) if separated else p)

    return " – ".join(new_places)


def _remove_subset_words(main, sub):
    main_seq_case = main.split()
    main_seq = main.lower().split()
    sub_seq = sub.lower().split()

    length = len(sub_seq)
    if length > len(main_seq):
        return main
    for i in range(len(main_seq) - length, -1, -1):
        if main_seq[i:i+length] == sub_seq:
            del main_seq_case[i:i+length]

    return " ".join(main_seq_case)


@utils.xslt_text_func
def short_description(_, text, remove_stop_words=False):
    without_brackets = BRACKETS.sub(" ", text)
    places = without_brackets.split(" – ")

    if remove_stop_words:
        new_places = []
        to_remove = ["and", "circular", "in", "or", "of", "the", "via",
                     "town centre", "city centre"]
        for p in places:
            for s in to_remove:
                p = _remove_subset_words(p, s)
            new_places.append(p)

        places = [p for p in new_places if p]

    if not places:
        return without_brackets

    while len(places) > 1 and places[0] == places[-1]:
        del places[-1]

    if len(places) > 1:
        return f"{places[0]} – {places[-1]}"
    else:
        return places[0]


class ServiceCodes:
    """ Creates unique codes, keeping track of region and lines passed. """
    NON_WORDS = re.compile(r"[^A-Za-z0-9.]+")

    def __init__(self):
        self._unique = collections.defaultdict(int)
        utils.xslt_text_func(self.service_code)

    def service_code(self, _, line, description):
        """ Creates unique code based on line name and description. """
        line_name = self.NON_WORDS.sub("-", line.lower())
        components = [line_name]

        if len(line_name) <= 5:
            # Add description as shorter line name is less likely to be unique
            short_desc = short_description(None, description, True)
            components.append(self.NON_WORDS.sub("-", short_desc.lower()))

        key = "-".join(components)
        self._unique[key] += 1
        if self._unique[key] > 1:
            key += f"-{self._unique[key]}"

        return key


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

    if isinstance(nodes, et._Element):
        element = nodes
    elif nodes:
        element = nodes[0]
    else:
        element = None

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

    if isinstance(nodes, et._Element):
        element = nodes
    elif nodes and nodes[0]:
        element = nodes[0]
    else:
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
def bank_holidays(_, nodes, region):
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

    if isinstance(nodes, et._Element):
        element = nodes
    elif nodes:
        element = nodes[0]
    else:
        element = []

    hols = 0
    for d in element:
        hols |= holidays.get(et.QName(d).localname, 0)

    if region == "S":
        hols &= ~holidays["LateSummerBankHolidayNotScotland"]
    else:
        hols &= ~(
            holidays["Jan2ndScotland"] |
            holidays["AugustBankHolidayScotland"]
        )

    return hols


def setup_tnds_functions(connection):
    """ Finds all existing stop points in database, setting up XSLT functions.
    """
    query_operators = connection.execute(db.select([models.Operator.code]))
    query_stops = connection.execute(db.select([models.StopPoint.atco_code]))
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
    def stop_exists(_, file_, code):
        """ Check if stop point exists. """
        nonlocal set_not_exists
        exists = code in set_stops
        if not exists and code not in set_not_exists:
            set_not_exists.add(code)
            utils.logger.warning(f"Stop ATCO code {code!r} in file {file_!r} "
                                 f"does not exist.")

        return exists


def _delete_empty_services(connection):
    """ Delete services and associated operators if all stop point references
        are null - eg when including a metro route where all stop points are
        not in the existing database.
    """
    service = models.Service.__table__
    pattern = models.JourneyPattern.__table__
    link = models.JourneyLink.__table__
    local_operator = models.LocalOperator.__table__
    operator = models.Operator.__table__
    organisations = models.Organisations.__table__
    organisation = models.Organisation.__table__

    empty_patterns = ~db.exists().where(
        (link.c.pattern_ref == pattern.c.id) &
        link.c.stop_point_ref.isnot(None)
    )
    empty_services = ~db.exists().where(
        pattern.c.service_ref == service.c.id
    )
    empty_local = ~db.exists().where(
        (pattern.c.region_ref == operator.c.region_ref) &
        (pattern.c.local_operator_ref == local_operator.c.code)
    )
    empty_operators = ~db.exists().where(
        local_operator.c.operator_ref == operator.c.code
    )
    empty_orgs = ~db.exists().where(
        organisations.c.org_ref == organisation.c.code
    )

    with connection.begin():
        utils.logger.info("Querying journey patterns without stop point "
                          "references")
        # All associated journey links and journeys will be deleted too
        jp = connection.execute(pattern.delete().where(empty_patterns))
        utils.logger.info(f"JourneyPattern: {jp.rowcount} without stop "
                          f"point references deleted")

        s = connection.execute(service.delete().where(empty_services))
        utils.logger.info(f"Service: {s.rowcount} without journey patterns "
                          f"deleted")

        lo = connection.execute(local_operator.delete().where(empty_local))
        utils.logger.info(f"LocalOperator: {lo.rowcount} without journey "
                          f"patterns deleted")

        o = connection.execute(operator.delete().where(empty_operators))
        utils.logger.info(f"Operator: {o.rowcount} without local operators "
                          f"deleted")

        org = connection.execute(organisation.delete().where(empty_orgs))
        utils.logger.info(f"Organisation: {org.rowcount} without journeys "
                          f"deleted")


def populate_tnds_data(connection, directory=None, delete=True, warn=False):
    """ Commits TNDS data to database.

        :param connection: Connection for population.
        :param directory: Directory where zip files with TNDS XML documents and
        named after region codes are contained. If None, they will be
        downloaded.
        :param delete: Truncate all data from TNDS tables before populating.
        :param warn: Log warning if no FTP credentials exist. If False an error
        will be raised instead.
    """
    data = None
    if directory is None:
        regions = _get_regions(connection)
        try:
            # Download required files and get region code from each filename
            data = _download_tnds_files(regions)
        except ValueError:
            if warn:
                utils.logger.warn("No TNDS FTP credentials are specified in "
                                  "config; skipping over TNDS population.")
            else:
                raise
    else:
        regions = _get_regions(connection)
        data = {}
        for r in regions:
            file_ = r + ".zip"
            path = os.path.join(directory, file_)
            if os.path.exists(path):
                data[r] = path
            else:
                utils.logger.warning(f"Archive {file_!r} not found in "
                                     f"directory {directory!r}.")

    if not data:
        raise ValueError(
            "No files were passed - either the directory specified did not "
            "contain any suitable archives or their downloads failed."
        )

    setup_tnds_functions(connection)
    row_ids = RowIds(connection, check_existing=not delete)
    ServiceCodes()

    # We don't want to delete any NOC data if they have been added
    excluded = models.Operator, models.LocalOperator
    metadata = utils.reflect_metadata(connection)
    with open_binary("nextbus.populate", "tnds.xslt") as file_:
        xslt = et.XSLT(et.parse(file_))

    del_ = delete
    for region, archive in data.items():
        for file_ in file_ops.iter_archive(archive):
            path = os.path.join(os.path.basename(archive), file_.name)
            utils.logger.info(f"Parsing file {path!r}")
            data = utils.xslt_transform(file_, xslt, region=region,
                                        file=file_.name)
            utils.populate_database(
                connection,
                utils.collect_xml_data(data),
                metadata=metadata,
                delete=del_,
                exclude=excluded
            )
            row_ids.clear()
            del_ = False


def process_tnds_data(connection):
    _delete_empty_services(connection)
