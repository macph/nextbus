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

        # Register XSLT functions
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

    def add_id(self, _, name, *ids):
        """ Adds IDs (eg file name, code) to list, returning an integer ID. """
        if name not in self._id:
            # Find the initial sequence and set up list
            initial = self._get_sequence(name)
            utils.logger.info("Setting sequence for %s to %d" % (name, initial))

            self._id[name] = IndexList(initial=initial)

        return self._id[name].add(ids)

    def get_id(self, _, name, *ids):
        """ Gets integer ID for IDs (eg file name, code) """
        if name not in self._id or ids not in self._id[name]:
            raise ValueError("IDs %r does not exist for model %r." %
                             (ids, name))

        return self._id[name].get(ids)


@utils.xslt_text_func
def format_description(_, text):
    if text is not None and text.isupper():
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
    """ Finds all existing operators and stop points in database, setting up
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


def _delete_empty_services():
    """ Delete services and associated operators if all stop point references
        are null - eg when including a metro route where all stop points are
        not in the existing database.
    """
    empty_patterns = (
        db.session.query(models.JourneyLink.pattern_ref)
        .group_by(models.JourneyLink.pattern_ref)
        .having(models.JourneyLink.stop_point_ref.is_(None))
        .subquery()
    )
    empty_services = ~(
        db.session.query(models.JourneyPattern)
        .filter(models.JourneyPattern.service_ref == models.Service.code)
        .exists()
    )
    empty_local_operators = ~(
        db.session.query(models.Service)
        .filter(models.Service.region_ref == models.LocalOperator.region_ref,
                models.Service.local_operator_ref == models.LocalOperator.code)
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
        table = model.__table__
        db.session.execute(table.delete().where(where))

    with utils.database_session():
        utils.logger.info("Deleting services without stop point references")
        delete(models.JourneyPattern,
               models.JourneyPattern.id.in_(empty_patterns))
        delete(models.Service, empty_services)
        delete(models.LocalOperator, empty_local_operators)
        delete(models.Operator, empty_operators)
        delete(models.Organisation, empty_organisations)


def _services_add_admin_areas():
    """ Add administrative area code to each service.

        The code is chosen as the mode of all admin areas associated with stops
        on the route that are within the service region. For example, if a
        service based in the South East has 40% stops in the SE and 60% in
        London the admin area is picked from the mode of stops within the SE.
    """
    service_areas = (
        db.session.query(models.Service.code.label("service"),
                         models.AdminArea.code.label("admin_area"))
        .select_from(models.Service)
        .distinct()
        .join(models.Service.patterns)
        .join(models.JourneyPattern.links)
        .join(models.JourneyLink.stop)
        .join(models.StopPoint.admin_area)
        .filter(models.Service.region_ref == models.AdminArea.region_ref)
        .subquery()
    )
    set_sa = db.session.query(
        service_areas.c.service.label("service"),
        db.func.mode().within_group(service_areas.c.admin_area).label("mode")
    ).group_by(service_areas.c.service).subquery()

    with utils.database_session():
        utils.logger.info("Appending admin area references to services")
        service = models.Service.__table__
        statement = (
            service.update()
            .values(admin_area_ref=set_sa.c.mode)
            .where(service.c.code == set_sa.c.service)
        )
        db.session.execute(statement)


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


def commit_tnds_data(archive=None, region=None, delete=True):
    """ Commits TNDS data to database.

        :param archive: Path to a zipped archive with TNDS XML documents. If
        None, they will be downloaded.
        :param region: Region code for archive file.
        :param delete: Truncate all data from TNDS tables before populating.
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

    if delete:
        # Remove data from associated tables beforehand
        with utils.database_connection() as cursor:
            utils.truncate_tables(cursor, [
                models.Operator, models.LocalOperator, models.Service,
                models.JourneyPattern, models.JourneyLink, models.Journey,
                models.JourneySpecificLink, models.Organisation,
                models.OperatingDate, models.OperatingPeriod,
                models.Organisations, models.SpecialPeriod, models.BankHolidays
            ])

    transform = _get_tnds_transform()
    setup_tnds_functions()
    RowIds()
    for region, archive in regions.items():
        _commit_each_tnds(transform, archive, region)

    _delete_empty_services()
