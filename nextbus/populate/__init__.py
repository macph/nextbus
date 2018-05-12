"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
from nextbus.populate.nptg import commit_nptg_data
from nextbus.populate.naptan import commit_naptan_data
from nextbus.populate.nspl import commit_nspl_data
from nextbus.populate.modify import modify_data
