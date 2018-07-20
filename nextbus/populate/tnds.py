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


def _parse_operators():
    """ Filter out all existing national operators. """
    query_operators = db.session.query(models.Operator.code)
    set_operators = set(c.code for c in query_operators.all())

    def parse_operators(obj):
        if obj["code"] not in set_operators:
            return obj

    return parse_operators


def _parse_local_operators():
    """ Filter out all existing local operators. """
    query_local_op = db.session.query(models.LocalOperator.code,
                                      models.LocalOperator.region_ref)
    set_operators = set((c.code, c.region_ref) for c in query_local_op.all())

    def parse_local_operators(obj):
        if (obj["code"], obj["region_ref"]) not in set_operators:
            return obj

    return parse_local_operators


def _parse_journey_links():
    """ Checks starting and stopping points, removing references if they do
        not exist (eg are inactive or do not have valid NaPTAN codes).
    """
    query_stops = db.session.query(models.StopPoint.atco_code)
    set_stops = set(c.atco_code for c in query_stops.all())

    def parse_journey_links(obj):
        if obj["stop_start"] not in set_stops:
            obj["stop_start"] = None
        if obj["stop_end"] not in set_stops:
            obj["stop_end"] = None

        return obj

    return parse_journey_links


def _get_tnds_transform():
    """ Uses XSLT to convert TNDS XML data into several separate datasets. """
    tnds_xslt = et.parse(os.path.join(ROOT_DIR, TNDS_XSLT))
    transform = et.XSLT(tnds_xslt)

    return transform


def _commit_each_tnds(transform, archive, region):
    """ Transforms each XML file and commit data to DB. """
    str_region = et.XSLT.strparam(region)
    tnds = utils.DBEntries(log_each=False)

    parse_jl = _parse_journey_links()
    parse_no = _parse_operators()
    parse_lo = _parse_local_operators()

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
        tnds.add("OperatorGroup/Operator", models.Operator, indices=("code",),
                 func=parse_no)
        tnds.add("LocalOperatorGroup/LocalOperator", models.LocalOperator,
                 indices=("region_ref", "code"), func=parse_lo)
        tnds.add("ServiceGroup/Service", models.Service)
        tnds.add("ServiceLineGroup/ServiceLine", models.ServiceLine)
        tnds.add("JourneyPatternGroup/JourneyPattern", models.JourneyPattern)
        tnds.add("JourneySectionGroup/JourneySection", models.JourneySection)
        tnds.add("JourneySectionsGroup/JourneySections", models.JourneySections)
        tnds.add("JourneyLinkGroup/JourneyLink", models.JourneyLink,
                 func=parse_jl)
        tnds.add("JourneyGroup/Journey", models.Journey)
        tnds.add("OrganisationGroup/Organisation", models.Organisation,
                 indices=("code",))
        tnds.add("OperatingDateGroup/OperatingDate", models.OperatingDate)
        tnds.add("OperatingPeriodGroup/OperatingPeriod", models.OperatingPeriod)
        tnds.add("OrganisationsGroup/Organisations", models.Organisations)
        tnds.add("SpecialPeriodGroup/SpecialPeriod", models.SpecialPeriod)
        tnds.add("BankHolidaysGroup/BankHolidays", models.BankHolidays)

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
