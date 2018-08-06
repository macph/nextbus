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


def download_tnds_files():
    """ Download TNDS files from FTP server. """
    user = current_app.config.get("TNDS_USERNAME")
    password = current_app.config.get("TNDS_PASSWORD")
    if not user or not password:
        raise ValueError("The application config requires an username and "
                         "password to access the TNDS FTP server. See the "
                         "Traveline website for more details.")

    # Get all region codes to iterate over - not GB
    query_regions = (db.session.query(models.Region.code)
                     .filter(models.Region.code != "GB"))
    list_regions = [r[0] for r in query_regions.all()]
    if not list_regions:
        raise ValueError("NPTG data not populated yet.")

    paths = {}
    utils.logger.info("Opening FTP connection to %r with credentials" %
                      TNDS_URL)
    with ftplib.FTP(TNDS_URL, user=user, passwd=password) as ftp:
        for region in list_regions:
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
        return "<UniqueList(%s, initial=%s)>" % (items, self._initial)

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
        return self._iter()

    def _iter(self):
        """ Generator function to be used for iter() """
        for i in sorted(self._map.values()):
            for k, j in self._map.items():
                if i == j:
                    yield k
                    break

    def add(self, item):
        """ Adds item to list, returning its index. If item is already in list,
            returns the existing item's index.
        """
        if item not in self._map:
            self._map[item] = self._current
            self._current += 1

        return self._map[item]

    def append(self, item):
        """ Appends item to list. If item is already in list, an error is
            raised.
        """
        if item not in self._map:
            self._map[item] = self._current
            self._current += 1
        else:
            raise KeyError(item)

    def get(self, item):
        """ Gets index of an item or None if it does not exist. """
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

        utils.xslt_text_func(self.add_id)
        utils.xslt_text_func(self.get_id)

    def _get_sequence(self, model_name):
        """ Check database to find max value to start from or use 1. """
        start = 1
        if self.existing:
            # Get maximum ID integer from table and start off from there
            model = getattr(models, model_name)
            query = db.session.query(db.func.max(model.id)).one()
            if query[0] is not None:
                start = query[0] + 1

        return start

    def add_id(self, _, name, file_name, *ids):
        """ Adds file name + code/ID to list, returning an integer ID. """
        if name not in self._id:
            # Find the initial sequence and set up list
            initial = self._get_sequence(name)
            utils.logger.info("Setting sequence for %s to %d" %
                              (name, initial))

            self._id[name] = IndexList(initial=initial)

        return self._id[name].add((file_name, *ids))

    def get_id(self, _, name, file_name, *ids):
        """ Gets integer ID for a file name and code/ID. """
        if name in self._id and (file_name, *ids) in self._id[name]:
            return self._id[name].get((file_name, *ids))
        else:
            print(self._id)
            raise ValueError("ID %r does not exist for file %r and model %r." %
                             (ids, file_name, name))


@utils.xslt_text_func
def format_description(_, text):
    if text is not None and text.isupper():
        text = utils.capitalize(None, text)

    places = text.split(" - ")
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


@utils.xslt_text_func
def format_operator(_, text):
    if text is not None and text.isupper():
        text = utils.capitalize(None, text)

    return text


@utils.xslt_func
def days_week(_, nodes=None):
    """ Gets days of week from a RegularDayType element.

        Returned as an integer with Monday-Sunday corresponding to bits 1-7. If
        nodes is None Monday-Friday is returned as the default.
    """
    week = 0
    mon, tues, wed, thurs, fri, sat, sun = range(1, 8)

    def set_days(first, last=None):
        """ Sets bits for an inclusive range of days. """
        nonlocal week
        last_ = last if last is not None else first
        for i in range(first, last_ + 1):
            week |= 1 << i

    try:
        element = nodes[0]
    except IndexError:
        element = None
    except TypeError:
        element = nodes

    if element is None:
        # Default is Monday to Friday
        set_days(mon, fri)
        return week

    ns = {"txc": element.xpath("namespace-uri(.)")}
    xpath = et.XPathElementEvaluator(element, namespaces=ns)

    if xpath("txc:DaysOfWeek[txc:MondayToSunday]"):
        set_days(mon, sun)
        return week

    if xpath("txc:DaysOfWeek[txc:Weekend]"):
        set_days(sat, sun)
        return week

    if xpath("txc:DaysOfWeek[txc:Sunday]"):
        set_days(sun)

    if xpath("txc:DaysOfWeek[txc:NotSaturday]"):
        set_days(sun)
        set_days(mon, fri)
        return week

    if xpath("txc:DaysOfWeek[txc:MondayToSaturday]"):
        set_days(mon, sat)
        return week

    if xpath("txc:DaysOfWeek[txc:Saturday]"):
        set_days(sat)

    if xpath("txc:DaysOfWeek[txc:MondayToFriday]"):
        set_days(mon, fri)
        return week

    if xpath("txc:DaysOfWeek[txc:Monday]"):
        set_days(mon)
    if xpath("txc:DaysOfWeek[txc:Tuesday]"):
        set_days(tues)
    if xpath("txc:DaysOfWeek[txc:Wednesday]"):
        set_days(wed)
    if xpath("txc:DaysOfWeek[txc:Thursday]"):
        set_days(thurs)
    if xpath("txc:DaysOfWeek[txc:Friday]"):
        set_days(fri)

    return week


@utils.xslt_func
def weeks_month(_, nodes):
    """ Gets weeks of month from a PeriodicDayType element.

        Returned as an integer with first to fifth weeks corresponding to bits
        0-4. If no weeks are found, None is returned.
    """
    weeks = {
        "first": 0,
        "second": 1,
        "third": 2,
        "fourth": 3,
        "fifth": 4,
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
            number = int(w.text) - 1
        except (TypeError, ValueError):
            number = weeks[w.text.lower()]
        month |= 1 << number

    return month if month > 0 else None


def setup_tnds_functions():
    """ Finds all existing operators and stop points in database, seting up
        XSLT functions compare with incoming operators and journey links.
    """
    query_operators = db.session.query(models.Operator.code)
    query_local = db.session.query(models.LocalOperator.code,
                                   models.LocalOperator.region_ref)
    query_stops = db.session.query(models.StopPoint.atco_code)
    set_national = set(c.code for c in query_operators.all())
    set_local = set((c.code, c.region_ref) for c in query_local.all())
    set_stops = set(c.atco_code for c in query_stops.all())
    set_not_exists = set()

    @utils.xslt_text_func
    def national_op_new(_, code):
        """ Check if national operator does not exist.. """
        return bool(code) and code not in set_national

    @utils.xslt_text_func
    def local_op_new(_, code, region_ref):
        """ Check if local operator does not exist. """
        return all([code, region_ref, (code, region_ref) not in set_local])

    @utils.xslt_text_func
    def stop_exists(_, code):
        """ Check if stop point exists. """
        nonlocal set_not_exists
        exists = code in set_stops
        if not exists and code not in set_not_exists:
            set_not_exists.add(code)
            utils.logger.warning("Stop code %r does not exist." % code)

        return exists


def _get_tnds_transform():
    """ Uses XSLT to convert TNDS XML data into several separate datasets. """
    tnds_xslt = et.parse(os.path.join(ROOT_DIR, TNDS_XSLT))
    transform = et.XSLT(tnds_xslt)

    return transform


def _commit_each_tnds(transform, archive, region):
    """ Transforms each XML file and commit data to DB. """
    str_region = et.XSLT.strparam(region)
    tnds = utils.PopulateData()

    for file_ in file_ops.iter_archive(archive):
        utils.logger.info("Parsing file %r" % os.path.join(archive, file_.name))
        data = et.parse(file_)
        file_name = et.XSLT.strparam(file_.name)

        try:
            new_data = transform(data, region=str_region, file=file_name)
        except et.XSLTError as err:
            for error_message in getattr(err, "error_log"):
                utils.logger.error(error_message)
            raise

        tnds.set_data(new_data)
        tnds.add("Operator", models.Operator, indices=("code",))
        tnds.add("LocalOperator", models.LocalOperator,
                 indices=("region_ref", "code"))
        tnds.add("Service", models.Service, indices=("code",))
        tnds.add("JourneyPattern", models.JourneyPattern)
        tnds.add("JourneyLink", models.JourneyLink)
        tnds.add("Journey", models.Journey)
        tnds.add("JourneySpecificLink", models.JourneySpecificLink)
        tnds.add("Organisation", models.Organisation, indices=("code",))
        tnds.add("OperatingDate", models.OperatingDate)
        tnds.add("OperatingPeriod", models.OperatingPeriod)
        tnds.add("Organisations", models.Organisations)
        tnds.add("SpecialPeriod", models.SpecialPeriod)
        tnds.add("BankHolidays", models.BankHolidays)

    tnds.commit(delete=False)


def commit_tnds_data(archive=None, region=None):
    """ Commits TNDS data to database.

        :param archive: Path to a zipped archive with TNDS XML documents. If
        None, they will be downloaded.
        :param region: Region code for archive file.
    """
    if archive is None:
        # Download required files and get region code from each filename
        regions = download_tnds_files()
    elif region is None:
        raise TypeError("A region code must be specified for archive %s."
                        % archive)
    else:
        # Use archive and associated region code
        regions = {region: archive}

    transform = _get_tnds_transform()
    setup_tnds_functions()
    RowIds()
    for region, archive in regions.items():
        _commit_each_tnds(transform, archive, region)
