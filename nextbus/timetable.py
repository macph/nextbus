"""
Creating timetables for a service.
"""
from collections import abc
import functools

from nextbus import db, graph, models


_ZERO = db.bindparam("zero", 0)
_HOUR = db.bindparam("hour", "1 hour")
_GB_TZ = db.bindparam("gb", "Europe/London")
_UTC_TZ = db.bindparam("utc", "UTC")
_TRUNCATE_MIN = db.bindparam("trunc_min", "minute")
_FORMAT_TIME = db.bindparam("format_time", "HH24MI")


def _in_bit_array(array, col):
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

    # Find week of month (0 to 4) and day of week (Monday 1 to Sunday 7)
    week = db.cast(db.extract("DAY", p_date), db.Integer) / 7
    weekday = db.cast(db.extract("ISODOW", p_date), db.Integer)

    # PostgreSQL can repeat or skip times over daylight savings time changes in
    # a time series so we generate timestamps from 1 hour before to 1 hour after
    # and exclude times not matching the original departure time
    one_hour = db.cast(_HOUR, db.Interval)
    departures = db.func.generate_series(
        db.func.timezone(_GB_TZ, p_date + models.Journey.departure) - one_hour,
        db.func.timezone(_GB_TZ, p_date + models.Journey.departure) + one_hour,
        one_hour,
    ).alias("departures")
    departure = db.column("departures")

    include_bank_holiday = db.aliased(models.BankHolidayDate)
    exclude_bank_holiday = db.aliased(models.BankHolidayDate)

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
        # Match special period if they fall within date range
        .outerjoin(
            models.SpecialPeriod,
            (models.Journey.id == models.SpecialPeriod.journey_ref) &
            (models.SpecialPeriod.date_start <= p_date) &
            (models.SpecialPeriod.date_end >= p_date)
        )
        # Match bank holidays on the same day
        .outerjoin(
            include_bank_holiday,
            _in_bit_array(
                models.Journey.include_holidays,
                include_bank_holiday.holiday_ref
            ) & (include_bank_holiday.date == p_date)
        )
        .outerjoin(
            exclude_bank_holiday,
            _in_bit_array(
                models.Journey.exclude_holidays,
                exclude_bank_holiday.holiday_ref
            ) & (exclude_bank_holiday.date == p_date)
        )
        # Match organisations working/holiday periods - can be operational
        # during holiday or working periods associated with organisation so
        # working attributes need to match (eg journey running during holidays
        # must match with operating periods for holidays or vice versa)
        .outerjoin(
            models.Organisations,
            models.Journey.id == models.Organisations.journey_ref
        )
        .outerjoin(
            models.Organisation,
            models.Organisations.org_ref == models.Organisation.code
        )
        .outerjoin(
            models.OperatingPeriod,
            (models.Organisation.code == models.OperatingPeriod.org_ref) &
            (models.Organisations.working == models.OperatingPeriod.working) &
            (models.OperatingPeriod.date_start <= p_date) &
            (models.OperatingPeriod.date_end.is_(None) |
             (models.OperatingPeriod.date_end >= p_date))
        )
        .outerjoin(
            models.ExcludedDate,
            (models.Organisation.code == models.ExcludedDate.org_ref) &
            (models.Organisations.working == models.ExcludedDate.working) &
            (models.ExcludedDate.date == p_date)
        )
        .filter(
            # Match journey patterns on service ID and direction
            models.JourneyPattern.service_ref == p_service_id,
            models.JourneyPattern.direction.is_(p_direction),
            # Date must be within range for journey pattern, may be unbounded
            models.JourneyPattern.date_start <= p_date,
            models.JourneyPattern.date_end.is_(None) |
            (models.JourneyPattern.date_end >= p_date),
            # Filter out generated times 1 hour before and after departures
            db.extract("HOUR", db.func.timezone(_GB_TZ, departure)) ==
            db.extract("HOUR", models.Journey.departure),
            # In order of precedence:
            # - Do not run on special days
            # - Do not run on bank holidays
            # - Run on special days
            # - Run on bank holidays
            # - Do not run during organisation working or holiday periods
            # - Run during organisation working or holiday periods
            # - Run or not run on specific weeks of month
            # - Run or not run on specific days of week
            models.SpecialPeriod.id.isnot(None) |
            include_bank_holiday.date.isnot(None) |
            (models.Journey.weeks.is_(None) |
             _in_bit_array(models.Journey.weeks, week)) &
            _in_bit_array(models.Journey.days, weekday)
        )
        .group_by(models.Journey.id, departure)
        # Bank holidays and special dates have precedence over others so only
        # include journeys if all references are either null or are operational
        # Include non-null references in WHERE so they can be checked here
        # Check organisation working/holiday periods here after grouping as
        # there can be multiple periods for an organisation.
        .having(db.func.bool_and(
            db.case([
                (models.SpecialPeriod.id.isnot(None),
                 models.SpecialPeriod.operational),
                (exclude_bank_holiday.holiday_ref.isnot(None), db.false()),
                (include_bank_holiday.holiday_ref.isnot(None), db.true()),
                (models.OperatingPeriod.id.isnot(None) &
                 models.ExcludedDate.id.is_(None),
                 models.Organisations.operational)
            ], else_=db.true())
        ))
    )

    return journeys


def _query_times(service_id, direction, date):
    """ Queries all times for journeys on a specific day. """
    journeys = _query_journeys(service_id, direction, date).cte("journeys")

    zero = db.cast("0", db.Interval)
    # For each link, add running and wait intervals from journey-specific link,
    # journey pattern link or zero if both are null
    sum_coalesced_times = db.func.sum(
        db.func.coalesce(
            models.JourneySpecificLink.run_time,
            models.JourneyLink.run_time, zero
        ) +
        db.func.coalesce(
            models.JourneySpecificLink.wait_arrive,
            models.JourneyLink.wait_arrive, zero
        ) +
        db.func.coalesce(
            models.JourneySpecificLink.wait_leave,
            models.JourneyLink.wait_leave, zero
        )
    )

    # Find last sequence number for each journey pattern
    last_sequence = (
        db.func.max(models.JourneyLink.sequence)
        .over(partition_by=(journeys.c.journey_id, journeys.c.departure))
    )

    # Sum all running and wait intervals from preceding rows plus this row's
    # running interval for arrival time
    time_arrive = (
        journeys.c.departure +
        sum_coalesced_times.over(
            partition_by=(journeys.c.journey_id, journeys.c.departure),
            order_by=models.JourneyLink.sequence,
            rows=(None, -1)
        ) +
        db.func.coalesce(
            models.JourneySpecificLink.run_time,
            models.JourneyLink.run_time, zero
        )
    )

    # Sum all running and wait intervals from preceding rows and this row
    time_depart = (
        journeys.c.departure +
        sum_coalesced_times.over(
            partition_by=(journeys.c.journey_id, journeys.c.departure),
            order_by=models.JourneyLink.sequence,
            rows=(None, 0)
        )
    )

    jl_start = db.aliased(models.JourneyLink)
    jl_end = db.aliased(models.JourneyLink)

    times = (
        db.session.query(
            journeys.c.journey_id,
            journeys.c.departure,
            models.LocalOperator.code.label("local_operator_code"),
            models.Operator.code.label("operator_code"),
            models.Operator.name.label("operator_name"),
            models.Journey.note_code,
            models.Journey.note_text,
            models.JourneyLink.stop_point_ref,
            models.JourneyLink.timing_point,
            # Journey may call or not call at this stop point
            db.func.coalesce(
                models.JourneySpecificLink.stopping,
                models.JourneyLink.stopping
            ).label("stopping"),
            models.JourneyLink.sequence,
            # Find arrival time if not first stop in journey
            db.case([(models.JourneyLink.sequence == 1, None)],
                    else_=time_arrive).label("time_arrive"),
            # Find departure time if not last stop in journey
            db.case([(models.JourneyLink.sequence == last_sequence, None)],
                    else_=time_depart).label("time_depart"),
        )
        .select_from(models.Journey)
        .join(journeys, models.Journey.id == journeys.c.journey_id)
        .join(models.Journey.pattern)
        .join(models.JourneyPattern.local_operator)
        .join(models.LocalOperator.operator)
        .join(models.JourneyPattern.links)
        .outerjoin(jl_start, models.Journey.start_run == jl_start.id)
        .outerjoin(jl_end, models.Journey.end_run == jl_end.id)
        .outerjoin(
            models.JourneySpecificLink,
            (models.Journey.id == models.JourneySpecificLink.journey_ref) &
            (models.JourneyLink.id == models.JourneySpecificLink.link_ref)
        )
        # Truncate journey pattern if journey has starting or ending dead runs
        .filter(
            jl_start.id.is_(None) |
            (models.JourneyLink.sequence >= jl_start.sequence),
            jl_end.id.is_(None) |
            (models.JourneyLink.sequence <= jl_end.sequence)
        )
    )

    return times


def _query_timetable(service_id, direction, date):
    """ Creates a timetable for a service in a set direction on a specific day.
    """
    times = _query_times(service_id, direction, date).cte("times")
    query = (
        db.session.query(
            times.c.journey_id,
            times.c.departure,
            times.c.local_operator_code,
            times.c.operator_code,
            times.c.operator_name,
            times.c.note_code,
            times.c.note_text,
            times.c.stop_point_ref,
            times.c.timing_point,
            db.func.timezone(_UTC_TZ, times.c.time_arrive).label("utc_arrive"),
            db.func.timezone(_UTC_TZ, times.c.time_depart).label("utc_depart"),
            _format_time(db.func.timezone(_GB_TZ, times.c.time_arrive))
            .label("arrive"),
            _format_time(db.func.timezone(_GB_TZ, times.c.time_depart))
            .label("depart")
        )
        .select_from(times)
        .filter(times.c.stop_point_ref.isnot(None), times.c.stopping)
        .order_by(times.c.departure, times.c.journey_id, times.c.sequence)
    )

    return query


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
