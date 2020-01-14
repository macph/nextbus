from nextbus import db, models
from nextbus.populate.file_ops import backup_database
from nextbus.populate.nptg import populate_nptg_data, process_nptg_data
from nextbus.populate.naptan import populate_naptan_data, process_naptan_data
from nextbus.populate.nspl import populate_nspl_data
from nextbus.populate.noc import populate_noc_data
from nextbus.populate.tnds import populate_tnds_data, process_tnds_data
from nextbus.populate.modify import modify_data
from nextbus.populate.utils import logger


def run_population(*, backup=False, backup_path=None, nptg=False,
                   nptg_path=None, naptan=False, naptan_path=False, nspl=False,
                   nspl_path=None, noc=False, noc_path=None, tnds=False,
                   tnds_directory=None, tnds_keep=False, tnds_warn_ftp=False,
                   modify=False, refresh=False):
    if backup:
        backup_database(backup_path)

    will_populate = any((nptg, naptan, nspl, noc, tnds))
    will_modify = will_populate or modify

    with db.engine.begin() as connection:
        if will_populate:
            dropped = models.drop_indexes(connection, exclude_unique=True)
        else:
            dropped = None

        if nptg:
            populate_nptg_data(connection, nptg_path)
        if naptan:
            populate_naptan_data(connection, naptan_path)
        if nspl:
            populate_nspl_data(connection, nspl_path)
        if noc:
            populate_noc_data(connection, noc_path)
        if tnds:
            populate_tnds_data(connection, tnds_directory,
                               delete=not tnds_keep, warn=tnds_warn_ftp)

        if dropped:
            models.restore_indexes(connection, dropped)

        if nptg:
            process_nptg_data(connection)
        if naptan:
            process_naptan_data(connection)
        if tnds:
            process_tnds_data(connection)
        if modify:
            modify_data(connection)

        if will_modify or refresh:
            logger.info("Refreshing derived models")
            models.refresh_derived_models(connection)
