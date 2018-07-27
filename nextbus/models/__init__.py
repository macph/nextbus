"""
Models subpackage.

All models for tables and materialized views are imported into this namespace,
such that external modules can call any model directly.
"""
from nextbus.models.tables import (
    Region, AdminArea, District, Locality, StopArea, StopPoint, Postcode,
    Operator, LocalOperator, Service, ServiceLine, JourneyPattern,
    JourneySections, JourneySection, JourneyLink, Journey, JourneySpecificLink,
    OperatingDate, OperatingPeriod, Organisation, Organisations, SpecialPeriod,
    BankHolidayDate, BankHolidays
)
from nextbus.models.mat_views import FTS
