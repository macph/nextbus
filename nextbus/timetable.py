"""
Creating timetables for a service.
"""
from collections import abc
import functools

from nextbus import db, graph, models


_ONE_HOUR = db.cast(db.literal_column("'1 hour'"), db.Interval)
_GB_TZ = db.bindparam("gb", "Europe/London")
_UTC_TZ = db.bindparam("utc", "UTC")
_TRUNCATE_MIN = db.bindparam("trunc_min", "minute")
_FORMAT_TIME = db.bindparam("format_time", "HH24MI")


def _bit_array_contains(array, col):
    """ SQL expression for matching integer with a bit array, equivalent to
        `(1 << col) & array > 0`.
    """
    return (
        db.literal_column("1").op("<<")(col).op("&")(array) >
        db.literal_column("0")
    )


def _format_time(timestamp):
    """ SQL expression to format a date or timestamp as `HHMM`, eg 0730. """
    return db.func.to_char(
        db.func.date_trunc(_TRUNCATE_MIN, timestamp),
        _FORMAT_TIME,
    )


def _get_departure_range(timestamp, name):
    """ Get reference to generated table with timestamp range between 1 hour
        before and 1 hour after the given timestamp (without time zone).

        This is used to include or exclude local timestamps if it happens to be
        within one of the DST changeover periods. Normally, there will be three
        timestamps (with time zone) with only the middle time used, but if it
        is, say, 0130 on the last Sunday of October the start and end times will
        be 0030 BST and 0230 GMT respectively, four hours apart. 0130 BST and
        0130 GMT can then be retained as they match 0130.
    """
    return db.func.generate_series(
        db.func.timezone(_GB_TZ, timestamp) - _ONE_HOUR,
        db.func.timezone(_GB_TZ, timestamp) + _ONE_HOUR,
        _ONE_HOUR,
    ).alias(name)


def _filter_journey_dates(query, date):
    """ Join multiple tables used to filter journeys by valid dates (eg week
        days, bank holidays or organisation working days).

        It is assumed the Journey and JourneyPattern models are in the FROM
        clause or joined, and the query is grouped by the journey ID.
    """
    # Aggregate the matching bank holidays and operational periods before
    # joining laterally. If they were joined first the query planner may pick a
    # slower plan to compensate for the row count 'blowing up', but in practice
    # the actual number of matching rows is very low.

    # Match special period if they fall within inclusive date range
    matching_periods = (
        db.select([
            db.func.bool_and(models.SpecialPeriod.operational)
            .label("is_operational")
        ])
        .select_from(models.SpecialPeriod)
        .where(
            models.SpecialPeriod.journey_ref == models.Journey.id,
            models.SpecialPeriod.date_start <= date,
            models.SpecialPeriod.date_end >= date,
        )
        .lateral("matching_periods")
    )
    query = query.join(matching_periods, db.true())

    # Match bank holidays on the same day
    matching_bank_holidays = (
        db.select([
            db.func.bool_and(
                _bit_array_contains(
                    models.Journey.include_holidays,
                    models.BankHolidayDate.holiday_ref,
                ),
            ).label("is_operational"),
            db.func.bool_or(
                _bit_array_contains(
                    models.Journey.exclude_holidays,
                    models.BankHolidayDate.holiday_ref,
                ),
            ).label("not_operational")
        ])
        .select_from(models.BankHolidayDate)
        .where(models.BankHolidayDate.date == date)
        .lateral("matching_bank_holidays")
    )
    query = query.join(matching_bank_holidays, db.true())

    # Match organisations working/holiday periods - can be operational
    # during holiday or working periods associated with organisation so
    # working attributes need to match (eg journey running during holidays
    # must match with operating periods for holidays or vice versa)
    matching_organisations = (
        db.select([
            db.func.bool_and(
                models.OperatingPeriod.id.isnot(None) &
                models.ExcludedDate.id.is_(None) &
                models.Organisations.operational
            ).label("is_operational"),
            db.func.bool_or(
                models.OperatingPeriod.id.isnot(None) &
                models.ExcludedDate.id.is_(None) &
                db.not_(models.Organisations.operational)
            ).label("not_operational")
        ])
        .select_from(models.Organisations)
        .join(
            models.Organisation,
            models.Organisations.org_ref == models.Organisation.code,
        )
        .join(
            models.OperatingPeriod,
            db.and_(
                models.Organisation.code == models.OperatingPeriod.org_ref,
                models.Organisations.working == models.OperatingPeriod.working,
                models.OperatingPeriod.date_start <= date,
                models.OperatingPeriod.date_end.is_(None) |
                (models.OperatingPeriod.date_end >= date),
            ),
        )
        .outerjoin(
            models.ExcludedDate,
            db.and_(
                models.Organisation.code == models.ExcludedDate.org_ref,
                models.Organisations.working == models.ExcludedDate.working,
                models.ExcludedDate.date == date,
            )
        )
        .where(models.Organisations.journey_ref == models.Journey.id)
        .lateral("matching_organisations")
    )
    query = query.join(matching_organisations, db.true())

    # Find week of month (0 to 4) and day of week (Monday 1 to Sunday 7)
    week = db.cast(db.extract("DAY", date), db.Integer) / db.literal_column("7")
    weekday = db.cast(db.extract("ISODOW", date), db.Integer)

    query = query.filter(
        # Date must be within range for journey pattern, may be unbounded
        models.JourneyPattern.date_start <= date,
        models.JourneyPattern.date_end.is_(None) |
        (models.JourneyPattern.date_end >= date),
        # In order of precedence:
        # - Do not run on special days
        # - Do not run on bank holidays
        # - Run on special days
        # - Run on bank holidays
        # - Do not run during organisation working or holiday periods
        # - Run during organisation working or holiday periods
        # - Run or not run on specific weeks of month
        # - Run or not run on specific days of week
        matching_periods.c.is_operational.isnot(None) |
        matching_bank_holidays.c.is_operational.isnot(None) |
        (models.Journey.weeks.is_(None) |
         _bit_array_contains(models.Journey.weeks, week)) &
        _bit_array_contains(models.Journey.days, weekday)
    )

    # Bank holidays and special dates have precedence over others so only
    # include journeys if all references are either null or are operational.
    # Include non-null references in WHERE so they can be checked here.
    # Check organisation working/holiday periods here after grouping as
    # there can be multiple periods for an organisation.
    query = query.having(db.func.bool_and(
        db.case([
            (matching_periods.c.is_operational.isnot(None),
             matching_periods.c.is_operational),
            (matching_bank_holidays.c.not_operational, db.false()),
            (matching_bank_holidays.c.is_operational, db.true()),
            (matching_organisations.c.not_operational, db.false()),
            (matching_organisations.c.is_operational, db.true()),
        ], else_=db.true())
    ))

    return query


def _query_journeys(service_id, direction, date):
    """ Creates query to find all IDs for journeys that run on a particular day.

        Journeys are included and excluded them by matching with special dates,
        bank holidays, date ranges associated with organisations, weeks of month
        and days of week.
    """
    # Set as parameters for SQL query - reduces repetition of dates
    p_service_id = db.bindparam("service", service_id)
    p_direction = db.bindparam("direction", direction)
    p_date = db.bindparam("date", date, type_=db.Date)

    departures = _get_departure_range(
        p_date + models.Journey.departure,
        "departures"
    )
    departure = db.column("departures")

    # Find all journeys and their departures
    journeys = (
        db.session.query(
            models.Journey.id.label("journey_id"),
            departure.label("departure")
        )
        .select_from(models.JourneyPattern)
        .join(models.JourneyPattern.journeys)
        # SQLAlchemy does not have CROSS JOIN so use INNER JOIN ON TRUE
        .join(departures, db.true())
        .filter(
            # Match journey patterns on service ID and direction
            models.JourneyPattern.service_ref == p_service_id,
            models.JourneyPattern.direction.is_(p_direction),
            # Filter out generated times 1 hour before and after departures
            db.extract("HOUR", db.func.timezone(_GB_TZ, departure)) ==
            db.extract("HOUR", models.Journey.departure),
        )
        .group_by(models.Journey.id, departure)
    )

    # Add filters for departure dates
    journeys = _filter_journey_dates(journeys, p_date)

    return journeys


def _query_timetable(service_id, direction, date):
    """ Creates a timetable for a service in a set direction on a specific day.
    """
    journeys = _query_journeys(service_id, direction, date).cte("times")
    # Join JSON record set on 'true' as SQLAlchemy does not support cross joins.
    data = models.Journey.record_set()

    arrive = journeys.c.departure + data.c.arrive
    depart = journeys.c.departure + data.c.depart

    query = (
        db.session.query(
            journeys.c.journey_id,
            journeys.c.departure,
            models.LocalOperator.code.label("local_operator_code"),
            models.Operator.code.label("operator_code"),
            models.Operator.name.label("operator_name"),
            models.Journey.note_code.label("note_code"),
            models.Journey.note_text.label("note_text"),
            data.c.stop_point_ref,
            data.c.timing_point,
            db.func.timezone(_UTC_TZ, arrive).label("utc_arrive"),
            db.func.timezone(_UTC_TZ, depart).label("utc_depart"),
            _format_time(db.func.timezone(_GB_TZ, arrive)).label("arrive"),
            _format_time(db.func.timezone(_GB_TZ, depart)).label("depart")
        )
        .select_from(journeys)
        .join(models.Journey, journeys.c.journey_id == models.Journey.id)
        .join(models.Journey.pattern)
        .join(models.JourneyPattern.local_operator)
        .join(models.LocalOperator.operator)
        .join(data, db.true())
        .filter(data.c.stop_point_ref.isnot(None), data.c.stopping)
        .order_by(journeys.c.departure, journeys.c.journey_id, data.c.sequence)
    )

    return query


def _query_journeys_at_stop(atco_code):
    """ Creates query for journeys stopping at a specified stop point. """
    p_atco_code = db.bindparam("atco_code", atco_code)

    data = models.Journey.record_set()
    query = (
        db.session.query(
            models.Journey.id,
            models.Journey.departure,
            data.c.depart.label("t_offset"),
        )
        .select_from(models.Journey)
        .join(models.Journey.pattern)
        .join(models.JourneyPattern.links)
        .join(
            data,
            db.and_(
                data.c.stopping,
                data.c.depart.isnot(None),
                models.JourneyLink.sequence == data.c.sequence,
            )
        )
        .filter(models.JourneyLink.stop_point_ref == p_atco_code)
    )

    return query


def _query_next_services(atco_code, timestamp=None, interval=None):
    """ Creates query for getting all services stopping at this stop point in an
        interval.
    """
    if timestamp is None:
        p_timestamp = db.func.now()
    elif timestamp.tzinfo is None:
        # Assume this is a local timestamp with GB timezone.
        p_timestamp = db.func.timezone(_GB_TZ, db.bindparam("timestamp", timestamp))
    else:
        p_timestamp = db.bindparam("timestamp", timestamp)

    if interval is None:
        p_interval = _ONE_HOUR
    else:
        param = db.bindparam("interval", interval)
        p_interval = db.cast(param, db.Interval)

    journey_match = _query_journeys_at_stop(atco_code).cte("journey_match")

    time_start = p_timestamp - journey_match.c.t_offset
    time_end = time_start + p_interval
    times = (
        db.select([
            time_start.label("utc_start"),
            time_end.label("utc_end"),
            db.func.timezone(_GB_TZ, time_start).label("local_start"),
            db.func.timezone(_GB_TZ, time_end).label("local_end"),
        ])
        .correlate(journey_match)
        .lateral("times")
    )

    local_start_date = db.cast(times.c.local_start, db.Date)
    local_end_date = db.cast(times.c.local_end, db.Date)
    local_start_time = db.cast(times.c.local_start, db.Time)
    local_end_time = db.cast(times.c.local_end, db.Time)

    journey_departure = (
        db.session.query(
            journey_match.c.id,
            journey_match.c.t_offset,
            times.c.utc_start,
            times.c.utc_end,
            db.case(
                (
                    (local_start_date == local_end_date) |
                    (journey_match.c.departure > local_start_time),
                    local_start_date
                ),
                else_=local_end_date,
            ).label("date"),
            journey_match.c.departure.label("time"),
        )
        .select_from(journey_match)
        .join(times, db.true())
        .filter(
            (local_start_date == local_end_date) &
            db.between(
                journey_match.c.departure,
                local_start_time,
                local_end_time
            ) |
            (local_start_date < local_end_date) &
            (
                (journey_match.c.departure > local_start_time) |
                (journey_match.c.departure < local_end_time)
            )
        )
        .cte("journey_departure")
    )

    utc_departures = _get_departure_range(
        journey_departure.c.date + journey_departure.c.time,
        "utc_departure",
    )
    utc_departure = db.column("utc_departure")

    journey_filter = _filter_journey_dates(
        db.session.query(
            journey_departure.c.id,
            (utc_departure + journey_departure.c.t_offset).label("expected")
        )
        .select_from(journey_departure)
        .join(
            utc_departures,
            db.between(
                utc_departure,
                journey_departure.c.utc_start,
                journey_departure.c.utc_end,
            )
        )
        .join(models.Journey, journey_departure.c.id == models.Journey.id)
        .join(models.Journey.pattern)
        .group_by(
            journey_departure.c.id,
            journey_departure.c.t_offset,
            utc_departure
        ),
        journey_departure.c.date,
    ).cte("journey_filter")

    query = (
        db.session.query(
            models.Service.line.label("line"),
            models.JourneyPattern.origin.label("origin"),
            models.JourneyPattern.destination.label("destination"),
            models.Operator.code.label("op_code"),
            models.Operator.name.label("op_name"),
            journey_filter.c.expected,
            db.cast(db.extract("EPOCH", journey_filter.c.expected - p_timestamp), db.Integer).label("seconds")
        )
        .select_from(journey_filter)
        .join(models.Journey, journey_filter.c.id == models.Journey.id)
        .join(models.Journey.pattern)
        .join(models.JourneyPattern.service)
        .join(models.JourneyPattern.operator)
        .order_by(journey_filter.c.expected)
    )

    return query


def get_next_services(atco_code, timestamp=None, interval=None):
    """ Get all services stopping at this stop point in an interval.
    """
    query = _query_next_services(atco_code, timestamp, interval)
    return query.all()


class TimetableStop:
    """ Represents a cell in the timetable with arrival, departure and timing
        status.
    """
    __slots__ = ("stop_point_ref", "arrive", "depart", "timing", "utc_arrive",
                 "utc_depart")

    def __init__(self, stop_point_ref, arrive, depart, timing_point, utc_arrive,
                 utc_depart):
        self.stop_point_ref = stop_point_ref
        self.arrive = arrive
        self.depart = depart
        self.timing = timing_point
        self.utc_arrive = utc_arrive
        self.utc_depart = utc_depart

    def __repr__(self):
        return (
            f"<TimetableStop({self.stop_point_ref!r}, {self.arrive!r}, "
            f"{self.depart!r}, {self.timing!r})>"
        )

    def __eq__(self, other):
        return all([
            self.stop_point_ref == other.stop_point_ref,
            self.arrive == other.arrive,
            self.depart == other.depart,
            self.timing == other.timing,
            self.utc_arrive == other.utc_arrive,
            self.utc_depart == other.utc_depart
        ])

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def from_row(cls, row):
        """ Creates TimetableStop instance from row returned from query. """
        return cls(
            row.stop_point_ref,
            row.arrive,
            row.depart,
            row.timing_point,
            row.utc_arrive,
            row.utc_depart,
        )


class TimetableJourney(abc.MutableSequence):
    """ Journey for timetable, represented as one or more columns. """
    __slots__ = ("_stops", "_first")

    def __init__(self):
        self._stops = []
        self._first = None

    def __repr__(self):
        return f"<TimetableJourney({self.journey_id!r}, {self.departure!r})>"

    def __len__(self):
        return len(self._stops)

    def __getitem__(self, index):
        return self._stops[index]

    def __setitem__(self, index, value):
        self._check(value)
        self._stops[index] = TimetableStop.from_row(value)

    def __delitem__(self, index):
        del self._stops[index]
        if not self._stops:
            self._first = None

    @property
    def journey_id(self):
        return self._first.journey_id if self._first is not None else None

    @property
    def departure(self):
        return self._first.departure if self._first is not None else None

    @property
    def local_operator_code(self):
        return self._first.local_operator_code if self._first is not None else None

    @property
    def operator_name(self):
        return self._first.operator_name if self._first is not None else None

    @property
    def note_code(self):
        return self._first.note_code if self._first is not None else None

    @property
    def note_text(self):
        return self._first.note_text if self._first is not None else None

    def insert(self, index, value):
        self._check(value)
        self._stops.insert(index, TimetableStop.from_row(value))

    def _check(self, row):
        if len(self._stops) == 0:
            self._first = row
            return

        this = (
            self._first.journey_id,
            self._first.departure,
            self._first.local_operator_code,
            self._first.operator_name,
            self._first.note_code,
            self._first.note_text,
        )
        other = (
            row.journey_id,
            row.departure,
            row.local_operator_code,
            row.operator_name,
            row.note_code,
            row.note_text,
        )
        if this != other:
            raise ValueError(
                f"Row {row!r} does not match with journey attributes {this!r}"
            )

    def wrap(self, sequence):
        """ Wraps journey around sequence, adding extra columns and empty rows
            if necessary.
        """
        len_ = len(sequence)
        columns = [[]]
        index = 0
        col = 0

        for row in self:
            if row.stop_point_ref not in sequence:
                raise ValueError(
                    f"Row {row!r} stop point ref does not exist in sequence."
                )
            # Skip over sequence until the next stop in journey
            while index < len_ and row.stop_point_ref != sequence[index]:
                columns[col].append(None)
                index += 1
            # Add new column, starting the sequence over
            if index == len_:
                columns.append([])
                index = 0
                col += 1
            while row.stop_point_ref != sequence[index]:
                columns[col].append(None)
                index += 1

            columns[col].append(row)
            index += 1

        # After last stop, fill rest of sequence
        while index < len_:
            columns[col].append(None)
            index += 1

        return columns


class TimetableRow:
    """ Row in timetable with stop and timing status. """
    __slots__ = ("stop", "times", "timing")

    def __init__(self, stop, list_times):
        self.stop = stop
        self.times = list_times
        self.timing = any(t is not None and t.timing for t in self.times)

    def __repr__(self):
        return f"<TimetableRow({self.stop.atco_code!r}, {self.timing!r})>"


class Timetable:
    """ Creates a timetable for a service and direction.

        :param service_id: Service ID.
        :param direction: Direction of service - outbound if false, inbound if
        True.
        :param date: DateTime or Date object for a specific day to show this
        timetable for.
        :param sequence: Ordered list of stop point ATCO codes to construct
        timetable from. If this is None the sequence is generated from a graph.
        :param dict_stops: Dictionary of stop points. If this is None the
        dictionary is generated from this service.
        :param query_result: Use this result set to create timetable.
    """
    def __init__(self, service_id, direction, date, sequence=None,
                 dict_stops=None, query_result=None):
        self.service_id = service_id
        self.direction = direction
        self.date = date

        if sequence is None or dict_stops is None:
            g, stops = graph.service_graph_stops(service_id, direction)
            self.sequence = g.sequence()
            self.stops = stops
        else:
            self.sequence = list(sequence)
            self.stops = dict(dict_stops)

        self.head = []
        self.rows = []
        self.operators = {}
        self.notes = {}
        self.timed_rows = []

        if self.sequence:
            journeys = self._timetable_journeys(query_result)
            self._create_table(journeys)
            self.timed_rows = [r for r in self.rows if r.timing]

    def __repr__(self):
        return (
            f"<Timetable({self.service_id!r}, {self.direction!r}, "
            f"{self.date!r})>"
        )

    def __bool__(self):
        return bool(self.sequence)

    def _compare_times(self, journey_a, journey_b):
        """ Compares two journeys based on UTC arrival/departure times at their
            shared stops.
        """
        for code in self.sequence:
            try:
                row_a = next(r for r in journey_a if r.stop_point_ref == code)
                row_b = next(r for r in journey_b if r.stop_point_ref == code)
            except StopIteration:
                continue

            time_a = row_a.utc_depart or row_a.utc_arrive
            time_b = row_b.utc_depart or row_b.utc_arrive
            if time_a is None or time_b is None:
                continue
            elif time_a > time_b:
                return 1
            elif time_a < time_b:
                return -1

        return 0

    def _timetable_journeys(self, query_result=None):
        if query_result is not None:
            result = query_result
        else:
            query = _query_timetable(self.service_id, self.direction, self.date)
            result = query.all()

        dict_journeys = {}
        for row in result:
            if row.stop_point_ref not in self.stops:
                continue
            key = row.journey_id, row.departure
            if (journey := dict_journeys.get(key)) is not None:
                journey.append(row)
            else:
                journey = TimetableJourney()
                journey.append(row)
                dict_journeys[key] = journey

        return sorted(dict_journeys.values(),
                      key=functools.cmp_to_key(self._compare_times))

    def _create_table(self, journeys):
        head_journey = []
        head_operator = []
        head_note = []
        columns = []

        self.operators = {}
        self.notes = {}

        for j in journeys:
            wrapped = j.wrap(self.sequence)
            o_code = j.local_operator_code
            n_code = j.note_code

            if o_code is not None:
                self.operators[o_code] = j.operator_name
            if n_code is not None:
                self.notes[n_code] = j.note_text

            head_journey.append(j.journey_id)
            head_operator.append(o_code)
            head_note.append(n_code)
            columns.append(wrapped[0])

            for i in range(1, len(wrapped)):
                head_journey.append(None)
                head_operator.append(None)
                head_note.append(None)
                columns.append(wrapped[i])

        self.head = list(zip(head_journey, head_operator, head_note))
        self.rows = []
        for i, code in enumerate(self.sequence):
            stop = self.stops[code]
            self.rows.append(TimetableRow(stop, [c[i] for c in columns]))
