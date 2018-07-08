"""
Custom types, eg Enums, for relational models.
"""
from enum import Enum


class Direction(Enum):
    """ Enumeration for route direction. """
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INBOUND_OUTBOUND = "inboundAndOutbound"
    CIRCULAR = "circular"
    CLOCKWISE = "clockwise"
    ANTICLOCKWISE = "antiClockwise"


class ServiceMode(Enum):
    """ Mode of service (eg bus, metro) """
    BUS = "bus"
    UNDERGROUND = "underground"
    TRAM = "tram"


class ServiceAvailability(Enum):
    """ Times of day the service runs at. """
    ALL = "all"
    NIGHT = "night"
    OFF_PEAK = "off_peak"
    PEAK = "peak"
    DAYTIME = "daytime"


class StopTiming(Enum):
    """ Timing used at stop. """
    PPT = "PPT"  # principal point
    PTP = "PTP"  # principal & timing imfo point
    TIP = "TIP"  # time info point
    OTH = "OTH"  # other stop point


class BankHoliday(Enum):
    """ Bank holiday labels. """
    NEW_YEARS_DAY = "NewYearsDay"
    JAN_2ND = "Jan2ndScotland"
    GOOD_FRIDAY = "GoodFriday"
    EASTER_MONDAY = "EasterMonday"
    MAY_DAY = "MayDay"
    SPRING_BANK = "SpringBank"
    LATE_SUMMER = "LateSummerHolidayNotScotland"
    AUGUST_BANK = "AugustBankHolidayScotland"
    CHRISTMAS_DAY = "ChristmasDay"
    BOXING_DAY = "BoxingDay"
    CHRISTMAS_DAY_OFF = "ChristmasDayHoliday"
    BOXING_DAY_OFF = "BoxingDayHoliday"
    NEW_YEARS_OFF = "NewYearsDayHoliday"
    CHRISTMAS_EVE = "ChristmasEve"
    NEW_YEARS_EVE = "NewYearsEve"
