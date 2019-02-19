"""
Creating timetables for a service.
"""
from collections import abc
import functools

from nextbus import db, graph, models


def _in_bit_array(array, col):
    """ SQL expression for matching integer with a bit array, equivalent to
        `(1 << col) & array > 0`.
    """
    return db.literal_column("1").op("<<")(col).op("&")(array) > 0


def _set_timezone(timestamp, timezone):
    """ Sets timestamp to a timezone specified, eg 'Europe/London'.

        This operator has precedence over others such as +.
    """
    return timestamp.op("AT TIME ZONE", 100)(timezone)


def _format_time(timestamp):
    """ SQL expression to format a date or timestamp as `HHMM`, eg 0730. """
    trunc_min = db.bindparam("trunc_min", "minute")
    fmt_time = db.bindparam("format_time", "HH24MI")

    return db.func.to_char(db.func.date_trunc(trunc_min, timestamp), fmt_time)


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
    week = db.cast(db.func.floor(db.extract("DAY", p_date) / 7), db.Integer)
    weekday = db.cast(db.extract("ISODOW", p_date), db.Integer)

    # Add timezones BST, GMT and Europe/London (which can be either)
    timezones = models.utils.values(
        [db.column("tz", type_=db.Text)],
        ("BST",), ("GMT",), ("Europe/London",),
        alias_name="timezones"
    )

    # Set each journey departure to the correct timezone
    departure = _set_timezone(p_date + models.Journey.departure,
                              timezones.c.tz)

    # Find all journeys and their departures
    journeys = (
        db.session.query(models.Journey.id.label("journey_id"),
                         departure.label("departure"))
        .select_from(models.JourneyPattern, timezones)
        .join(models.Journey,
              models.JourneyPattern.id == models.Journey.pattern_ref)
        # Match special period if they fall within date range
        .outerjoin(models.SpecialPeriod,
                   (models.Journey.id == models.SpecialPeriod.journey_ref) &
                   (models.SpecialPeriod.date_start <= p_date) &
                   (models.SpecialPeriod.date_end >= p_date))
        # Match bank holidays on the same day
        .outerjoin(models.BankHolidays,
                   models.Journey.id == models.BankHolidays.journey_ref)
        .outerjoin(models.BankHolidayDate,
                   _in_bit_array(models.BankHolidays.holidays,
                                 models.BankHolidayDate.holiday_ref) &
                   (models.BankHolidayDate.date == p_date))
        # Match organisations working/holiday periods - can be operational
        # during holiday or working periods associated with organisation so
        # working attributes need to match (eg journey running during holidays
        # must match with operating periods for holidays or vice versa)
        .outerjoin(models.Organisations,
                   models.Journey.id == models.Organisations.journey_ref)
        .outerjoin(models.Organisation,
                   models.Organisations.org_ref == models.Organisation.code)
        .outerjoin(models.OperatingPeriod,
                   (models.Organisation.code == models.OperatingPeriod.org_ref)
                   & (models.Organisations.working ==
                      models.OperatingPeriod.working) &
                   (models.OperatingPeriod.date_start <= p_date) &
                   (models.OperatingPeriod.date_end >= p_date))
        .outerjoin(models.OperatingDate,
                   (models.Organisation.code == models.OperatingDate.org_ref) &
                   (models.Organisations.working ==
                    models.OperatingDate.working) &
                   (models.OperatingDate.date == p_date))
        .filter(
            # Match journey patterns on service ID and direction
            models.JourneyPattern.service_ref == p_service_id,
            models.JourneyPattern.direction.is_(p_direction),
            # Date must be within range for journey pattern, may be unbounded
            models.JourneyPattern.date_start <= p_date,
            models.JourneyPattern.date_end.is_(None) |
            (models.JourneyPattern.date_end >= p_date),
            # Check to see if departure falls within 0100 and 0200 when timezone
            # changes on last Sunday of March or October
            # If in March, this journey is skipped.
            # If in October, this journey is repeated in both BST and GMT.
            # Otherwise Europe/London is picked, setting BST/GMT automatically.
            db.case([
                ((db.extract("MONTH", p_date) == 3) &
                 (db.extract("DAY", p_date) > 24) &
                 (db.extract("ISODOW", p_date) == 7) &
                 (db.extract("HOUR", models.Journey.departure) == 1), False),
                ((db.extract("MONTH", p_date) == 10) &
                 (db.extract("DAY", p_date) > 24) &
                 (db.extract("ISODOW", p_date) == 7) &
                 (db.extract("HOUR", models.Journey.departure) == 1),
                 (timezones.c.tz == "BST") | (timezones.c.tz == "GMT"))
            ], else_=timezones.c.tz == "Europe/London"),
            # In order of precedence:
            # - Do not run on bank holidays or special dates (check with HAVING)
            # - Run on bank holidays or special dates
            # - Do not run during organisation working/holiday periods
            # - Run during organisation working or holiday periods
            # - Run on specific weeks of month
            # - Run on specific days of week
            (models.SpecialPeriod.id.isnot(None) &
             models.SpecialPeriod.operational) |
            (models.BankHolidayDate.date.isnot(None) &
             models.BankHolidays.operational) |
            (models.Organisations.org_ref.is_(None) |
             models.Organisations.operational) &
            (models.Journey.weeks.is_(None) |
             _in_bit_array(models.Journey.weeks, week)) &
            _in_bit_array(models.Journey.days, weekday)
        )
        .group_by(models.Journey.id, departure)
        # Exclusion from bank holidays or special dates take precedence over
        # others so only include journey if neither bank holiday or special
        # period have matching records excluding this date
        .having(db.func.bool_and(
            (models.SpecialPeriod.id.is_(None) |
             models.SpecialPeriod.operational) &
            (models.BankHolidayDate.date.is_(None) |
             models.BankHolidays.operational)
        ))
    )

    return journeys


def _query_times(service_id, direction, date):
    """ Queries all times for journeys on a specific day. """
    journeys = _query_journeys(service_id, direction, date).subquery("journeys")

    zero = db.cast("0", db.Interval)
    # For each link, add running and wait intervals from journey-specific link,
    # journey pattern link or zero if both are null
    sum_coalesced_times = db.func.sum(
        db.func.coalesce(models.JourneySpecificLink.run_time,
                         models.JourneyLink.run_time, zero) +
        db.func.coalesce(models.JourneySpecificLink.wait_arrive,
                         models.JourneyLink.wait_arrive, zero) +
        db.func.coalesce(models.JourneySpecificLink.wait_leave,
                         models.JourneyLink.wait_leave, zero)
    )

    # Find last sequence number for each journey pattern
    last_sequence = db.func.first_value(models.JourneyLink.sequence).over(
        partition_by=(journeys.c.journey_id, journeys.c.departure),
        order_by=db.desc(models.JourneyLink.sequence)
    )

    # Sum all running and wait intervals from preceding rows plus this row's
    # running interval for arrival time
    time_arrive = journeys.c.departure + sum_coalesced_times.over(
        partition_by=(journeys.c.journey_id, journeys.c.departure),
        order_by=models.JourneyLink.sequence,
        rows=(None, -1)
    ) + db.func.coalesce(models.JourneySpecificLink.run_time,
                         models.JourneyLink.run_time, zero)

    # Sum all running and wait intervals from preceding rows and this row
    time_depart = journeys.c.departure + sum_coalesced_times.over(
        partition_by=(journeys.c.journey_id, journeys.c.departure),
        order_by=models.JourneyLink.sequence,
        rows=(None, 0)
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
            db.func.coalesce(models.JourneySpecificLink.stopping,
                             models.JourneyLink.stopping).label("stopping"),
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
        .outerjoin(models.JourneySpecificLink)
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
    times = _query_times(service_id, direction, date).subquery("times")
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
            db.func.timezone("UTC", times.c.time_arrive).label("utc_arrive"),
            db.func.timezone("UTC", times.c.time_depart).label("utc_depart"),
            _format_time(db.func.timezone("Europe/London", times.c.time_arrive))
            .label("arrive"),
            _format_time(db.func.timezone("Europe/London", times.c.time_depart))
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

    def __init__(self, row_data):
        self.stop_point_ref = row_data.stop_point_ref
        self.arrive = row_data.arrive
        self.depart = row_data.depart
        self.timing = row_data.timing_point
        self.utc_arrive = row_data.utc_arrive
        self.utc_depart = row_data.utc_depart

    def __repr__(self):
        return "<TimetableStop(%r, %r, %r, %r)>" % (
            self.stop_point_ref, self.arrive, self.depart, self.timing
        )


class TimetableJourney(abc.MutableSequence):
    """ Journey for timetable, represented as one or more columns.

        :param first_row: First row from query from which journey ID, departure
        time, etc is taken.
        :param other_rows: Extra rows to add to this journey.
        :param add: If False, the specified rows will not be added at start and
        will need to be appended separately.
    """
    def __init__(self, first_row, *other_rows, add=True):
        self.journey_id = first_row.journey_id
        self.departure = first_row.departure
        self.operator = first_row.local_operator_code, first_row.operator_name
        self.note = first_row.note_code, first_row.note_text

        self._stops = []
        if add:
            self._stops.append(TimetableStop(first_row))
            for row in other_rows:
                self.append(TimetableStop(row))

    def __repr__(self):
        return "<TimetableJourney(%r, %r, %r, %r)>" % (
            self.journey_id, self.departure, self.operator, self.note
        )

    def __len__(self):
        return len(self._stops)

    def __getitem__(self, index):
        return self._stops[index]

    def __setitem__(self, index, value):
        self._check(value)
        self._stops[index] = TimetableStop(value)

    def __delitem__(self, index):
        del self._stops[index]

    def insert(self, index, value):
        self._check(value)
        self._stops.insert(index, TimetableStop(value))

    def _check(self, row):
        if any([self.journey_id != row.journey_id,
                self.departure != row.departure,
                self.operator != (row.local_operator_code, row.operator_name),
                self.note != (row.note_code, row.note_text)]):
            raise ValueError(
                "Row %r does not match with journey attributes %r" % (
                    row,
                    (self.journey_id, self.departure, self.operator, self.note)
                )
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
                raise ValueError("Row %r stop point ref does not exist in "
                                 "sequence." % row)
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
    """ Row in timetable with stop point ref and timing status. """
    __slots__ = "stop_point_ref", "times", "timing"

    def __init__(self, stop_point_ref, list_times):
        self.stop_point_ref = stop_point_ref
        self.times = list_times
        self.timing = any(t is not None and t.timing for t in self.times)

    def __repr__(self):
        return "<TimetableRow(%r, %r)>" % (self.stop_point_ref, self.timing)


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
            g, ds = graph.service_graph_stops(service_id, direction)
            self.sequence = g.sequence() if sequence is None else list(sequence)
            self.stops = ds if dict_stops is None else dict(dict_stops)
        else:
            self.sequence = list(sequence)
            self.stops = dict(dict_stops)

        # Remove null values from start or end of sequence
        if self.sequence[0] is None:
            del self.sequence[0]
        if self.sequence[-1] is None:
            del self.sequence[-1]

        self.journeys = self._timetable_journeys(query_result)
        self.head, self.rows, self.operators, self.notes = self._create_table()

    def __repr__(self):
        return "<Timetable(%r, %r, %r)>" % (self.service_id, self.direction,
                                            self.date)

    def _compare_times(self, journey_a, journey_b):
        """ Compares two journeys based on UTC arrival/departure times at their
            shared stops.
        """
        for stop in self.sequence:
            try:
                row_a = next(r for r in journey_a if r.stop_point_ref == stop)
                row_b = next(r for r in journey_b if r.stop_point_ref == stop)
            except StopIteration:
                continue

            time_a = row_a.utc_arrive or row_a.utc_depart
            time_b = row_b.utc_arrive or row_b.utc_depart
            if time_a is None or time_b is None:
                continue
            if time_a != time_b:
                return 1 if time_a > time_b else -1

        return 0

    def _timetable_journeys(self, query_result=None):
        dict_journeys = {}
        query = _query_timetable(self.service_id, self.direction, self.date)
        result = query.all() if query_result is None else query_result

        for row in result:
            dict_journeys.setdefault(
                (row.journey_id, row.departure),
                TimetableJourney(row, add=False)
            ).append(row)

        return sorted(dict_journeys.values(),
                      key=functools.cmp_to_key(self._compare_times))

    def _create_table(self):
        head_journey = []
        head_operator = []
        head_note = []
        columns = []

        operators = {}
        notes = {}

        for j in self.journeys:
            wrapped = j.wrap(self.sequence)
            empty = [None] * (len(wrapped) - 1)

            head_journey.extend([j.journey_id] + empty)

            o_code, o_name = j.operator
            head_operator.extend([o_code] + empty)
            if o_code is not None:
                operators[o_code] = o_name

            n_code, n_text = j.note
            head_note.extend([n_code] + empty)
            if n_code is not None:
                notes[n_code] = n_text

            columns.extend(wrapped)

        head = list(zip(head_journey, head_operator, head_note))
        rows = []
        for i, stop in enumerate(self.sequence):
            rows.append(TimetableRow(stop, [c[i] for c in columns]))

        return head, rows, operators, notes
