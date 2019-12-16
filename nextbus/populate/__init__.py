"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
from nextbus.populate.file_ops import backup_database, restore_database
from nextbus.populate.nptg import commit_nptg_data
from nextbus.populate.naptan import commit_naptan_data
from nextbus.populate.nspl import commit_nspl_data
from nextbus.populate.noc import commit_noc_data
from nextbus.populate.tnds import commit_tnds_data
from nextbus.populate.modify import modify_data
