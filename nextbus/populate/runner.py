from nextbus import db, models
from nextbus.populate.file_ops import backup_database
from nextbus.populate.holidays import populate_holiday_data
from nextbus.populate.nptg import populate_nptg_data, process_nptg_data
from nextbus.populate.naptan import populate_naptan_data, process_naptan_data
from nextbus.populate.nspl import populate_nspl_data
from nextbus.populate.noc import populate_noc_data
from nextbus.populate.tnds import populate_tnds_data, process_tnds_data
from nextbus.populate.modify import modify_data
from nextbus.populate.utils import lock_all_tables, logger


def run_population(*, backup=False, backup_path=None, nptg=False,
                   nptg_path=None, naptan=False, naptan_path=False, nspl=False,
                   nspl_path=None, noc=False, noc_path=None, tnds=False,
                   tnds_path=None, tnds_keep=False, tnds_warn_ftp=False,
                   modify=False, refresh=False):
    if backup:
        backup_database(backup_path)

    will_populate = any((nptg, naptan, nspl, noc, tnds))
    will_modify = will_populate or modify

    if will_populate:
        dropped = models.drop_indexes(exclude_unique=True, include_missing=True)
        try:
            with db.engine.begin() as connection:
                lock_all_tables(connection)
                if nptg:
                    populate_nptg_data(connection, nptg_path)
                if naptan:
                    populate_naptan_data(connection, naptan_path)
                if nspl:
                    populate_nspl_data(connection, nspl_path)
                if noc:
                    populate_noc_data(connection, noc_path)
                if tnds:
                    populate_holiday_data(connection)
                    populate_tnds_data(connection, tnds_path,
                                       delete=not tnds_keep, warn=tnds_warn_ftp)
        finally:
            if dropped:
                models.restore_indexes(indexes=dropped)

    if will_modify:
        with db.engine.begin() as connection:
            if nptg:
                process_nptg_data(connection)
            if naptan:
                process_naptan_data(connection)
            if tnds:
                process_tnds_data(connection)
            if modify:
                modify_data(connection)

    if will_modify or refresh:
        with db.engine.begin() as connection:
            logger.info("Refreshing derived models")
            models.refresh_derived_models(connection)
