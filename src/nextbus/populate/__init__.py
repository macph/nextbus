"""
Populating database with data from NPTG, NaPTAN and NSPL.
"""
from nextbus.populate.file_ops import backup_database, restore_database
from nextbus.populate.runner import run_population
