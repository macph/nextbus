"""
Populate bus route and timetable data from TNDS.
"""
import ftplib
import os

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


def setup_tnds_xslt_functions():
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

    @utils.xslt_func
    @utils.ext_function_text
    def national_op_new(_, code):
        """ Check if national operator does not exist.. """
        return code not in set_national

    @utils.xslt_func
    @utils.ext_function_text
    def local_op_new(_, code, region_ref):
        """ Check if local operator does not exist. """
        return (code, region_ref) not in set_local

    @utils.xslt_func
    @utils.ext_function_text
    def stop_exists(_, code):
        """ Check if stop point exists. """
        return code in set_stops


def _get_tnds_transform():
    """ Uses XSLT to convert TNDS XML data into several separate datasets. """
    tnds_xslt = et.parse(os.path.join(ROOT_DIR, TNDS_XSLT))
    transform = et.XSLT(tnds_xslt)

    return transform


def _commit_each_tnds(transform, archive, region):
    """ Transforms each XML file and commit data to DB. """
    str_region = et.XSLT.strparam(region)
    tnds = utils.PopulateData()
    setup_tnds_xslt_functions()

    for file_ in file_ops.iter_archive(archive):
        utils.logger.info("Parsing file %r for region %r" %
                          (file_.name, region))
        data = et.parse(file_)
        try:
            new_data = transform(data, region=str_region)
        except (et.XSLTParseError, et.XSLTApplyError) as err:
            for error_message in getattr(err, "error_log"):
                utils.logger.error(error_message)
            raise

        tnds.set_data(new_data)
        tnds.add("Operator", models.Operator, indices=("code",))
        tnds.add("LocalOperator", models.LocalOperator,
                 indices=("region_ref", "code"))
        tnds.add("Service", models.Service)
        tnds.add("ServiceLine", models.ServiceLine)
        tnds.add("JourneyPattern", models.JourneyPattern)
        tnds.add("JourneySection", models.JourneySection)
        tnds.add("JourneySections", models.JourneySections)
        tnds.add("JourneyLink", models.JourneyLink)
        tnds.add("Journey", models.Journey)
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
    for region, archive in regions.items():
        _commit_each_tnds(transform, archive, region)
