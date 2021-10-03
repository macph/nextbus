"""
Models subpackage.

All models for tables and materialized views are imported into this namespace,
such that external modules can call any model directly.
"""
from nextbus.models.utils import *
from nextbus.models.tables import *
from nextbus.models.derived import *


@db.event.listens_for(db.MetaData, "before_create")
def define_collation(_, connection, **kw):
    """ Define the numeric collation required for some text columns. """
    connection.execute(
        "CREATE COLLATION IF NOT EXISTS utf8_numeric "
        "(provider = icu, locale = 'en@colNumeric=yes')"
    )
