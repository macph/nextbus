"""
Creating timetables for a service.
"""
import functools

from nextbus import db, graph, models
from nextbus.models import utils


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
    timezones = utils.values(
        [db.column("tz", type_=db.Text)],
        ("BST",), ("GMT",), ("Europe/London",),
        alias_name="timezones"
    )

    # Set each journey departure to the correct timezone
    departure = _set_timezone(p_date + models.Journey.departure,
                              timezones.c.tz)

    # Find all journeys and their departures
    journeys = (
        db.session.query(models.Journey.id.label("id"),
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

    zero = db.bindparam("zero", "0", type_=db.Interval)
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
        partition_by=(journeys.c.id, journeys.c.departure),
        order_by=db.desc(models.JourneyLink.sequence)
    )

    # Sum all running and wait intervals from preceding rows plus this row's
    # running interval for arrival time
    time_arrive = journeys.c.departure + sum_coalesced_times.over(
        partition_by=(journeys.c.id, journeys.c.departure),
        order_by=models.JourneyLink.sequence,
        rows=(None, -1)
    ) + db.func.coalesce(models.JourneySpecificLink.run_time,
                         models.JourneyLink.run_time, zero)

    # Sum all running and wait intervals from preceding rows and this row
    time_depart = journeys.c.departure + sum_coalesced_times.over(
        partition_by=(journeys.c.id, journeys.c.departure),
        order_by=models.JourneyLink.sequence,
        rows=(None, 0)
    )

    jl_start = db.aliased(models.JourneyLink)
    jl_end = db.aliased(models.JourneyLink)

    times = (
        db.session.query(
            models.Journey.id.label("journey_id"),
            models.Journey.note_code,
            models.Journey.note_text,
            models.LocalOperator.code.label("local_operator_code"),
            models.Operator.name.label("operator_name"),
            journeys.c.departure,
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
        .join(journeys, models.Journey.id == journeys.c.id)
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
            times.c.note_code,
            times.c.note_text,
            times.c.local_operator_code,
            times.c.operator_name,
            times.c.departure,
            times.c.stop_point_ref,
            times.c.timing_point,
            times.c.stopping,
            db.func.timezone("UTC", times.c.time_arrive).label("utc_arrive"),
            db.func.timezone("UTC", times.c.time_depart).label("utc_depart"),
            _format_time(db.func.timezone("Europe/London", times.c.time_arrive))
            .label("arrive"),
            _format_time(db.func.timezone("Europe/London", times.c.time_depart))
            .label("depart")
        )
        .select_from(times)
        .filter(times.c.stop_point_ref.isnot(None))
        .order_by(times.c.departure, times.c.journey_id, times.c.sequence)
    )

    return query


class Timetable:
    """ Creates a timetable for a service and a direction.

        :param service_id: Service ID.
        :param direction: Direction of service - outbound if false, inbound if
        True.
        :param date: DateTime or Date object for a specific day to show this
        timetable for.
        :param sequence: Ordered list of stop point ATCO codes to construct
        timetable from. If this is None the sequence is generated from a graph.
        :param dict_stops: Dictionary of stop points. If this is None the
        dictionary is generated from this service.
    """
    def __init__(self, service_id, direction, date, sequence=None,
                 dict_stops=None):
        self.service_id = service_id
        self.direction = direction
        self.date = date

        # Generate new dict and list of stops or use existing dict and list
        if sequence is None or dict_stops is None:
            service = models.Service.query.get(self.service_id)
            if service is None:
                raise ValueError("Service %r does not exist." % self.service_id)

            graph_, stops = graph.service_graph_stops(self.service_id,
                                                      self.direction)
            self.stops = stops if dict_stops is None else dict_stops
            self.sequence = graph_.sequence() if sequence is None else sequence
        else:
            self.stops = dict(dict_stops)
            self.sequence = list(sequence)

        # Remove null values from start or end of sequence
        if self.sequence[0] is None:
            del self.sequence[0]
        if self.sequence[-1] is None:
            del self.sequence[-1]

        self.head = []
        self.operators = {}
        self.notes = {}
        self.times = {c: list() for c in self.sequence}

        query = _query_timetable(self.service_id, self.direction, self.date)
        self.data = list(query.all())

        self._sort_times()
        self._fill_table()

    def _compare_times(self, a, b):
        """ Compares two journeys based on UTC arrival/departure times at their
            shared stops.
        """
        for stop in self.sequence:
            ar = next((ar for ar in a if ar.stop_point_ref == stop), None)
            br = next((br for br in b if br.stop_point_ref == stop), None)
            if ar is None or br is None:
                continue

            at = ar.utc_depart or ar.utc_arrive
            bt = br.utc_depart or br.utc_arrive
            if at is not None and bt is not None and at != bt:
                return 1 if at > bt else -1

        return 0

    def _sort_times(self):
        """ Sorts journeys by arrivals/departures in UTC at shared stops.

            For example, Journey 1 starts from point A at 0700 and stops at
            point B at 0730, and Journey 2 starts from point B at 0715. Journey
            2 should be placed before Journey 1 because it leaves point B
            earlier.
        """
        dict_groups = {}
        for row in self.data:
            # Group by departure time as well, a journey may be repeated
            identifier = row.journey_id, row.departure.timestamp()
            dict_groups.setdefault(identifier, list()).append(row)

        groups = sorted(dict_groups.values(),
                        key=functools.cmp_to_key(self._compare_times))

        self.data = [row for g in groups for row in g]

    def _append_empty_rows(self, start, end):
        """ Appends an empty cell to each row in a range. """
        for i in range(start, end):
            self.times[self.sequence[i]].append(None)

    def _fill_table(self):
        """ Fills table using data from query. """
        current = 0
        journeys = set()
        len_sequence = len(self.sequence)

        for r in self.data:
            if r.journey_id not in journeys:
                if current != 0:
                    # Need to fill previous column before moving to new one
                    self._append_empty_rows(current, len_sequence)
                    current = 0

                self.head.append((r.journey_id, r.local_operator_code,
                                  r.note_code))
                self.operators[r.local_operator_code] = r.operator_name
                if r.note_code is not None:
                    self.notes[r.note_code] = r.note_text
                journeys.add(r.journey_id)

            index = self.sequence.index(r.stop_point_ref)
            if index > current:
                # Skip over rows to next stop
                self._append_empty_rows(current, index)
            elif index < current:
                # Stop appears in earlier row - skip over rest of rows, back to
                # start then skip over to that row
                self._append_empty_rows(current, len_sequence)
                self.head.append(None)
                self._append_empty_rows(0, index)

            self.times[r.stop_point_ref].append((r.arrive, r.depart,
                                                 r.timing_point))
            current = (index + 1) % len_sequence

        if current != 0:
            # Fill last column
            self._append_empty_rows(current, len_sequence)

    def to_json(self):
        """ Serialises the table data. """
        rows = []
        for c in self.sequence:
            if c is not None:
                rows.append({
                    "code": c,
                    "times": list(self.times[c]),
                    "timing": any(s is not None and s[2] for s in self.times[c])
                })

        return {
            "operators": sorted(self.operators.items()),
            "notes": sorted(self.notes.items()),
            "head": list(self.head),
            "stops": rows
        }


def get_timetable(*args, **kwargs):
    """ Get timetable in serialised form. """
    return Timetable(*args, **kwargs).to_json()
